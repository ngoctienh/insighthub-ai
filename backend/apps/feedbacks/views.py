import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsInternalTeam, IsPMOrAdmin
from apps.insights.models import InsightGroup
from apps.notifications.models import ActivityLog, Comment, Notification, Vote
from apps.notifications.serializers import ActivityLogSerializer, CommentSerializer
from apps.notifications.services import (
    log_activity,
    notify_feedback_assigned,
    notify_feedback_received,
    notify_feedback_status_changed,
    notify_user,
)
from .models import Feedback, FeedbackSource, FeedbackTag, Product, Tag
from .serializers import (
    FeedbackDetailSerializer,
    FeedbackListSerializer,
    FeedbackSourceSerializer,
    FeedbackWriteSerializer,
    MultiSourceIngestSerializer,
    ProductSerializer,
    TagSerializer,
)

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("owner").annotate(
        feedback_count=Count("feedbacks", distinct=True)
    )
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsPMOrAdmin()]


class FeedbackSourceViewSet(viewsets.ModelViewSet):
    serializer_class = FeedbackSourceSerializer
    queryset = FeedbackSource.objects.annotate(
        feedback_count=Count("feedbacks", distinct=True)
    )
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsPMOrAdmin()]


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsPMOrAdmin()]


class FeedbackViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = user.role_code

        qs = (
            Feedback.objects.select_related(
                "product",
                "source",
                "assigned_to",
                "assigned_to__role",
                "author",
                "duplicate_of",
            )
            .prefetch_related("tags", "insight_groups")
            .annotate(annotated_votes_count=Count("votes", distinct=True))
        )

        # Role-based row-level data isolation enforced in backend
        if role == Role.CUSTOMER:
            qs = qs.filter(Q(author=user) | Q(sender_email__iexact=user.email))
        elif role == Role.DEVELOPER:
            qs = qs.filter(
                Q(assigned_to=user) | Q(insight_groups__assigned_to=user)
            ).distinct()
        # ADMIN, PRODUCT_MANAGER, CUSTOMER_SUPPORT can view full inbox

        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(code__icontains=search)
                | Q(title__icontains=search)
                | Q(content__icontains=search)
                | Q(sender_name__icontains=search)
                | Q(sender_email__icontains=search)
            )

        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("source"):
            qs = qs.filter(source__code=params["source"])
        if params.get("impact_level"):
            qs = qs.filter(impact_level=params["impact_level"])
        if params.get("product"):
            qs = qs.filter(product_id=params["product"])
        if params.get("assigned_to"):
            if params["assigned_to"] == "unassigned":
                qs = qs.filter(assigned_to__isnull=True)
            else:
                qs = qs.filter(assigned_to_id=params["assigned_to"])
        if params.get("tag"):
            tag_param = params["tag"]
            if str(tag_param).isdigit():
                qs = qs.filter(tags__id=int(tag_param))
            else:
                qs = qs.filter(tags__slug=tag_param)

        priority_level = params.get("priority_level")
        if priority_level == "CRITICAL":
            qs = qs.filter(Q(priority_score__gte=80) | Q(impact_level="CRITICAL"))
        elif priority_level == "HIGH":
            qs = qs.filter(Q(priority_score__gte=60, priority_score__lt=80) | Q(impact_level="HIGH"))
        elif priority_level == "MEDIUM":
            qs = qs.filter(Q(priority_score__gte=40, priority_score__lt=60) | Q(impact_level="MEDIUM"))
        elif priority_level == "LOW":
            qs = qs.filter(Q(priority_score__lt=40) | Q(impact_level="LOW"))

        if params.get("date_from"):
            d = parse_date(params["date_from"])
            if d:
                qs = qs.filter(submitted_at__date__gte=d)
        if params.get("date_to"):
            d = parse_date(params["date_to"])
            if d:
                qs = qs.filter(submitted_at__date__lte=d)

        if params.get("unclustered_only") in ("1", "true", "True"):
            qs = qs.filter(insight_links__isnull=True)
        if params.get("duplicate_only") in ("1", "true", "True"):
            qs = qs.filter(Q(status=Feedback.STATUS_DUPLICATE) | Q(duplicate_of__isnull=False))
        if params.get("mine_only") in ("1", "true", "True"):
            qs = qs.filter(Q(author=user) | Q(assigned_to=user))

        ordering = params.get("ordering", "-submitted_at")
        allowed_orderings = {
            "-submitted_at",
            "submitted_at",
            "-priority_score",
            "priority_score",
            "-id",
            "id",
        }
        if ordering in allowed_orderings:
            qs = qs.order_by(ordering, "-id")
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FeedbackWriteSerializer
        if self.action == "retrieve":
            return FeedbackDetailSerializer
        return FeedbackListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save()
        log_activity(
            request.user,
            ActivityLog.ENTITY_FEEDBACK,
            feedback.id,
            "CREATED",
            f"Tạo feedback {feedback.code} từ kênh {feedback.source.name}",
            new_value={"status": feedback.status, "impact_level": feedback.impact_level},
        )
        notify_feedback_received(feedback, actor=request.user)
        return Response(
            FeedbackDetailSerializer(feedback, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        feedback = self.get_object()
        role = request.user.role_code

        # Check object-level RBAC before applying edits
        if role == Role.CUSTOMER:
            if feedback.author_id != request.user.id:
                return Response(
                    {"detail": "Bạn chỉ được chỉnh sửa phản hồi của chính mình."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if feedback.status != Feedback.STATUS_NEW:
                return Response(
                    {"detail": "Chỉ có thể chỉnh sửa phản hồi khi đang ở trạng thái NEW."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            allowed_keys = {"title", "content", "impact_level"}
            filtered_data = {k: v for k, v in request.data.items() if k in allowed_keys}
        elif role in (Role.DEVELOPER, Role.CUSTOMER_SUPPORT):
            allowed_keys = {"status", "impact_level", "tag_ids"}
            if role == Role.CUSTOMER_SUPPORT:
                allowed_keys |= {"assigned_to"}
            filtered_data = {k: v for k, v in request.data.items() if k in allowed_keys}
            if not filtered_data:
                return Response(
                    {"detail": "Bạn chỉ có quyền cập nhật trạng thái xử lý hoặc gắn nhãn trên feedback này."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            filtered_data = request.data

        old_status = feedback.status
        old_assignee_id = feedback.assigned_to_id

        serializer = self.get_serializer(feedback, data=filtered_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        if old_status != updated.status:
            log_activity(
                request.user,
                ActivityLog.ENTITY_FEEDBACK,
                updated.id,
                "STATUS_CHANGED",
                f"Đổi trạng thái {updated.code}: {old_status} → {updated.status}",
                old_value={"status": old_status},
                new_value={"status": updated.status},
            )
            notify_feedback_status_changed(updated, old_status, updated.status, actor=request.user)

        if old_assignee_id != updated.assigned_to_id and updated.assigned_to_id:
            log_activity(
                request.user,
                ActivityLog.ENTITY_FEEDBACK,
                updated.id,
                "ASSIGNED",
                f"Phân công {updated.code} cho {updated.assigned_to.display_name()}",
            )
            notify_feedback_assigned(updated, updated.assigned_to, actor=request.user)

        return Response(FeedbackDetailSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        feedback = self.get_object()
        role = request.user.role_code
        if role in (Role.ADMIN, Role.PRODUCT_MANAGER):
            return super().destroy(request, *args, **kwargs)
        if role == Role.CUSTOMER and feedback.author_id == request.user.id and feedback.status == Feedback.STATUS_NEW:
            return super().destroy(request, *args, **kwargs)
        return Response(
            {"detail": "Bạn không có quyền xóa phản hồi này."},
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def assign(self, request, pk=None):
        feedback = self.get_object()
        if request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER, Role.CUSTOMER_SUPPORT):
            return Response(
                {"detail": "Bạn không có quyền phân công người phụ trách."},
                status=status.HTTP_403_FORBIDDEN,
            )
        assignee_id = request.data.get("assigned_to")
        assignee = None
        if assignee_id:
            assignee = User.objects.filter(id=assignee_id, is_active=True).first()
            if not assignee:
                return Response({"detail": "Người được phân công không tồn tại."}, status=status.HTTP_400_BAD_REQUEST)
        feedback.assigned_to = assignee
        feedback.save(update_fields=["assigned_to", "updated_at"])

        log_activity(
            request.user,
            ActivityLog.ENTITY_FEEDBACK,
            feedback.id,
            "ASSIGNED",
            f"Phân công {feedback.code} cho {assignee.display_name() if assignee else 'Chưa gán'}",
        )
        if assignee:
            notify_feedback_assigned(feedback, assignee, actor=request.user)
        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def tags(self, request, pk=None):
        feedback = self.get_object()
        tag_ids = request.data.get("tag_ids", [])
        if not isinstance(tag_ids, list):
            return Response({"detail": "tag_ids phải là danh sách ID."}, status=status.HTTP_400_BAD_REQUEST)
        FeedbackTag.objects.filter(feedback=feedback).exclude(tag_id__in=tag_ids).delete()
        for tag in Tag.objects.filter(id__in=tag_ids):
            FeedbackTag.objects.get_or_create(
                feedback=feedback,
                tag=tag,
                defaults={"added_by": request.user},
            )
        log_activity(
            request.user,
            ActivityLog.ENTITY_FEEDBACK,
            feedback.id,
            "TAGS_UPDATED",
            f"Cập nhật nhãn cho {feedback.code}",
        )
        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def mark_duplicate(self, request, pk=None):
        if request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER, Role.CUSTOMER_SUPPORT):
            return Response(
                {"detail": "Chỉ PM, Admin hoặc CS mới có quyền đánh dấu trùng lặp."},
                status=status.HTTP_403_FORBIDDEN,
            )
        feedback = self.get_object()
        target_id = request.data.get("duplicate_of_id")
        if not target_id or int(target_id) == feedback.id:
            return Response({"detail": "Cần chọn feedback gốc hợp lệ khác feedback hiện tại."}, status=status.HTTP_400_BAD_REQUEST)
        target = Feedback.objects.filter(id=target_id).first()
        if not target:
            return Response({"detail": "Feedback gốc không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        sim_score = request.data.get("similarity_score")
        feedback.duplicate_of = target
        feedback.similarity_score = float(sim_score) if sim_score is not None else feedback.similarity_score
        feedback.is_duplicate_confirmed = bool(request.data.get("confirm", True))
        if feedback.is_duplicate_confirmed:
            feedback.status = Feedback.STATUS_DUPLICATE
        feedback.save()

        log_activity(
            request.user,
            ActivityLog.ENTITY_FEEDBACK,
            feedback.id,
            "MARKED_DUPLICATE",
            f"Đánh dấu {feedback.code} trùng lặp với {target.code}",
        )
        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def unmark_duplicate(self, request, pk=None):
        feedback = self.get_object()
        feedback.duplicate_of = None
        feedback.is_duplicate_confirmed = False
        if feedback.status == Feedback.STATUS_DUPLICATE:
            feedback.status = Feedback.STATUS_NEW
        feedback.save()
        log_activity(
            request.user,
            ActivityLog.ENTITY_FEEDBACK,
            feedback.id,
            "UNMARKED_DUPLICATE",
            f"Gỡ đánh dấu trùng lặp cho {feedback.code}",
        )
        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def vote(self, request, pk=None):
        feedback = self.get_object()
        existing = Vote.objects.filter(user=request.user, feedback=feedback).first()
        if existing:
            existing.delete()
            voted = False
        else:
            Vote.objects.create(user=request.user, feedback=feedback)
            voted = True
        return Response({"voted": voted, "votes_count": feedback.votes.count()})

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        feedback = self.get_object()
        role = request.user.role_code
        if request.method == "GET":
            qs = feedback.comments.select_related("author", "author__role")
            if role == Role.CUSTOMER:
                qs = qs.filter(is_internal=False)
            return Response(CommentSerializer(qs, many=True).data)

        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"detail": "Nội dung bình luận không được để trống."}, status=status.HTTP_400_BAD_REQUEST)

        # Customers can never post internal-only notes
        is_internal = False if role == Role.CUSTOMER else bool(request.data.get("is_internal", False))
        comment = Comment.objects.create(
            author=request.user,
            feedback=feedback,
            content=content,
            is_internal=is_internal,
        )

        # Notify relevant party on public reply / customer update
        if not is_internal:
            if role == Role.CUSTOMER and feedback.assigned_to_id:
                notify_user(
                    recipient=feedback.assigned_to,
                    event_type=Notification.EVENT_COMMENT_ADDED,
                    title=f"Khách hàng bổ sung thông tin trên {feedback.code}",
                    message=content[:200],
                    actor=request.user,
                    feedback=feedback,
                    link_url=f"/inbox/{feedback.id}",
                )
            elif role != Role.CUSTOMER and feedback.author_id:
                notify_user(
                    recipient=feedback.author,
                    event_type=Notification.EVENT_COMMENT_ADDED,
                    title=f"Phản hồi mới từ đội ngũ sản phẩm về {feedback.code}",
                    message=content[:200],
                    actor=request.user,
                    feedback=feedback,
                    link_url=f"/inbox/{feedback.id}",
                )

        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def activity(self, request, pk=None):
        feedback = self.get_object()
        logs = ActivityLog.objects.select_related("actor").filter(
            entity_type=ActivityLog.ENTITY_FEEDBACK,
            entity_id=feedback.id,
        )
        return Response(ActivityLogSerializer(logs, many=True).data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def similar(self, request, pk=None):
        feedback = self.get_object()
        candidates = list(
            Feedback.objects.filter(product=feedback.product)
            .exclude(id=feedback.id)
            .order_by("-submitted_at")[:120]
        )
        if not candidates:
            return Response({"embedding_model": "none", "matches": []})

        payload = {
            "target": {
                "id": feedback.id,
                "code": feedback.code,
                "title": feedback.title,
                "content": feedback.content,
                "impact_level": feedback.impact_level,
                "votes_count": feedback.votes.count(),
                "sender_email": feedback.sender_email,
                "sender_name": feedback.sender_name,
                "source_code": feedback.source.code,
            },
            "candidates": [
                {
                    "id": item.id,
                    "code": item.code,
                    "title": item.title,
                    "content": item.content,
                    "impact_level": item.impact_level,
                    "votes_count": 0,
                    "sender_email": item.sender_email,
                    "sender_name": item.sender_name,
                    "source_code": item.source.code,
                }
                for item in candidates
            ],
            "top_k": int(request.query_params.get("top_k", 6)),
            "min_similarity": float(request.query_params.get("min_similarity", 0.35)),
            "use_llm": True,
        }

        headers = {}
        if settings.AI_SERVICE_API_KEY:
            headers["X-API-Key"] = settings.AI_SERVICE_API_KEY

        try:
            with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
                resp = client.post(
                    f"{settings.AI_SERVICE_URL}/similarity/search",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                return Response(resp.json())
        except Exception as exc:
            logger.warning("AI similarity search failed: %s", exc)
            return Response(
                {"detail": f"Không thể kết nối AI Service tại {settings.AI_SERVICE_URL}: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class MultiSourceIngestView(APIView):
    """
    Unified multi-source feedback ingestion endpoint (Web Form, Email, Live Chat, Community).
    Supports JWT-authenticated requests or external webhooks with X-Source-Token.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        source_token = request.headers.get("X-Source-Token", "").strip()
        is_authenticated = bool(request.user and request.user.is_authenticated)

        serializer = MultiSourceIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source = FeedbackSource.objects.filter(code=data["source_code"], is_active=True).first()
        if not source:
            return Response(
                {"detail": f"Nguồn phản hồi {data['source_code']} không tồn tại hoặc đang tắt."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_authenticated:
            if not source.webhook_token or source_token != source.webhook_token:
                return Response(
                    {"detail": "Yêu cầu xác thực JWT hoặc X-Source-Token hợp lệ."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        product = None
        if data.get("product_id"):
            product = Product.objects.filter(id=data["product_id"], is_active=True).first()
        if not product:
            product = Product.objects.filter(is_active=True).first()
        if not product:
            return Response(
                {"detail": "Chưa có sản phẩm nào hoạt động trong hệ thống."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        author = request.user if is_authenticated else None
        sender_name = (data.get("sender_name") or "").strip() or (
            author.display_name() if author else "Khách hàng"
        )
        sender_email = (data.get("sender_email") or "").strip() or (
            author.email if author else "guest@external-channel.local"
        )

        # If sender email matches a registered user, link author when submitted via external webhook
        if not author:
            author = User.objects.filter(email__iexact=sender_email).first()

        feedback = Feedback.objects.create(
            title=data["title"].strip(),
            content=data["content"].strip(),
            sender_name=sender_name,
            sender_email=sender_email,
            author=author,
            product=product,
            source=source,
            external_reference_id=data.get("external_reference_id", ""),
            source_metadata=data.get("source_metadata", {}),
            impact_level=data["impact_level"],
            status=Feedback.STATUS_NEW,
        )

        for tag in Tag.objects.filter(id__in=data.get("tag_ids", [])):
            FeedbackTag.objects.get_or_create(feedback=feedback, tag=tag)

        log_activity(
            author,
            ActivityLog.ENTITY_FEEDBACK,
            feedback.id,
            "INGESTED",
            f"Tiếp nhận phản hồi {feedback.code} từ kênh {source.name}",
            new_value={"source": source.code, "impact_level": feedback.impact_level},
        )
        notify_feedback_received(feedback, actor=author)

        return Response(
            FeedbackDetailSerializer(feedback, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role_code
        product_id = request.query_params.get("product")
        days = min(90, max(7, int(request.query_params.get("days", 30))))

        fb_qs = Feedback.objects.all()
        insight_qs = InsightGroup.objects.exclude(verification_status=InsightGroup.VERIFY_REJECTED)

        if product_id:
            fb_qs = fb_qs.filter(product_id=product_id)
            insight_qs = insight_qs.filter(product_id=product_id)

        if role == Role.CUSTOMER:
            fb_qs = fb_qs.filter(Q(author=user) | Q(sender_email__iexact=user.email))
        elif role == Role.DEVELOPER:
            fb_qs = fb_qs.filter(Q(assigned_to=user) | Q(insight_groups__assigned_to=user)).distinct()
            insight_qs = insight_qs.filter(assigned_to=user)

        total_feedbacks = fb_qs.count()
        new_feedbacks = fb_qs.filter(status=Feedback.STATUS_NEW).count()
        duplicate_feedbacks = fb_qs.filter(
            Q(status=Feedback.STATUS_DUPLICATE) | Q(is_duplicate_confirmed=True)
        ).count()

        if role == Role.CUSTOMER:
            insights_detected = 0
            in_progress_issues = fb_qs.filter(
                status__in=[Feedback.STATUS_PLANNED, Feedback.STATUS_IN_PROGRESS]
            ).count()
            completed_issues = fb_qs.filter(status=Feedback.STATUS_COMPLETED).count()
        else:
            insights_detected = insight_qs.count()
            in_progress_issues = insight_qs.filter(
                status__in=[InsightGroup.STATUS_ANALYZING, InsightGroup.STATUS_PLANNED, InsightGroup.STATUS_IN_PROGRESS]
            ).count()
            completed_issues = insight_qs.filter(status=InsightGroup.STATUS_COMPLETED).count()

        start_date = timezone.now() - timedelta(days=days - 1)
        by_date_rows = (
            fb_qs.filter(submitted_at__gte=start_date)
            .annotate(day=TruncDate("submitted_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        day_map = {row["day"].isoformat(): row["count"] for row in by_date_rows if row["day"]}
        feedbacks_by_date = []
        for offset in range(days):
            d = (start_date + timedelta(days=offset)).date().isoformat()
            feedbacks_by_date.append({"date": d, "count": day_map.get(d, 0)})

        source_rows = (
            fb_qs.values("source__code", "source__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        feedbacks_by_source = [
            {"source_code": r["source__code"], "name": r["source__name"], "count": r["count"]}
            for r in source_rows
        ]

        if role == Role.CUSTOMER:
            priority_rows = fb_qs.values("impact_level").annotate(count=Count("id"))
            priority_map = {r["impact_level"]: r["count"] for r in priority_rows}
        else:
            priority_rows = insight_qs.values("priority_level").annotate(count=Count("id"))
            priority_map = {r["priority_level"]: r["count"] for r in priority_rows}

        by_priority = [
            {"level": lvl, "count": priority_map.get(lvl, 0)}
            for lvl in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        ]

        top_5_issues = []
        urgent_insights = []
        if role != Role.CUSTOMER:
            top_5_qs = insight_qs.order_by("-feedback_count", "-priority_score")[:5]
            top_5_issues = [
                {
                    "id": ins.id,
                    "code": ins.code,
                    "title": ins.title,
                    "feedback_count": ins.feedback_count,
                    "affected_customers_count": ins.affected_customers_count,
                    "priority_score": ins.priority_score,
                    "priority_level": ins.priority_level,
                    "status": ins.status,
                }
                for ins in top_5_qs
            ]

            urgent_qs = (
                insight_qs.filter(priority_level__in=["CRITICAL", "HIGH"])
                .exclude(status=InsightGroup.STATUS_COMPLETED)
                .order_by("-priority_score")[:6]
            )
            urgent_insights = [
                {
                    "id": ins.id,
                    "code": ins.code,
                    "title": ins.title,
                    "priority_score": ins.priority_score,
                    "priority_level": ins.priority_level,
                    "feedback_count": ins.feedback_count,
                    "affected_customers_count": ins.affected_customers_count,
                    "status": ins.status,
                    "verification_status": ins.verification_status,
                    "due_date": ins.due_date.isoformat() if ins.due_date else None,
                }
                for ins in urgent_qs
            ]

        return Response(
            {
                "kpis": {
                    "total_feedbacks": total_feedbacks,
                    "new_feedbacks": new_feedbacks,
                    "insights_detected": insights_detected,
                    "in_progress_issues": in_progress_issues,
                    "completed_issues": completed_issues,
                    "duplicate_feedbacks": duplicate_feedbacks,
                },
                "feedbacks_by_date": feedbacks_by_date,
                "feedbacks_by_source": feedbacks_by_source,
                "by_priority": by_priority,
                "top_5_issues": top_5_issues,
                "urgent_insights": urgent_insights,
            }
        )
