import logging

from django.conf import settings
from django.db.models import Count
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsInternalTeam, IsPMOrAdmin, require_feature
from apps.insights.services import summarize_single_feedback
from apps.notifications.models import Vote
from apps.notifications.services import (
    notify_feedback_assigned,
    notify_feedback_received,
    notify_feedback_status_changed,
)
from .models import Feedback, FeedbackSource, FeedbackTag, Product, Tag
from .serializers import (
    FeedbackDetailSerializer,
    FeedbackListSerializer,
    FeedbackReplySerializer,
    FeedbackSourceSerializer,
    FeedbackWriteSerializer,
    MultiSourceIngestSerializer,
    ProductSerializer,
    TagSerializer,
)
from .services import (
    apply_feedback_filters,
    build_dashboard_data,
    find_similar_feedbacks,
    get_scoped_feedbacks,
    send_feedback_reply,
)

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.annotate(feedback_count=Count("feedbacks", distinct=True))
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsPMOrAdmin()]


class FeedbackSourceViewSet(viewsets.ModelViewSet):
    serializer_class = FeedbackSourceSerializer
    queryset = FeedbackSource.objects.annotate(feedback_count=Count("feedbacks", distinct=True))
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
    permission_classes = [permissions.IsAuthenticated, require_feature("inbox")]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "update", "partial_update", "vote"):
            return [permissions.IsAuthenticated(), require_feature("inbox", "kanban")()]
        return [p() for p in self.permission_classes]

    def get_queryset(self):
        qs = get_scoped_feedbacks(self.request.user)
        return apply_feedback_filters(qs, self.request.query_params, user=self.request.user)

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
        notify_feedback_received(feedback, actor=request.user)
        return Response(
            FeedbackDetailSerializer(feedback, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        feedback = self.get_object()
        role = request.user.role_code

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
            if not filtered_data:
                return Response(
                    {"detail": "Bạn chỉ được chỉnh sửa tiêu đề, nội dung hoặc mức ảnh hưởng khi phản hồi ở trạng thái NEW."},
                    status=status.HTTP_403_FORBIDDEN,
                )
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
            notify_feedback_status_changed(updated, old_status, updated.status, actor=request.user)

        if old_assignee_id != updated.assigned_to_id and updated.assigned_to_id:
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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam, require_feature("inbox")])
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

        if assignee:
            notify_feedback_assigned(feedback, assignee, actor=request.user)
        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam, require_feature("inbox")])
    def tags(self, request, pk=None):
        feedback = self.get_object()
        tag_ids = request.data.get("tag_ids", [])
        if not isinstance(tag_ids, list):
            return Response({"detail": "tag_ids phải là danh sách ID."}, status=status.HTTP_400_BAD_REQUEST)
        FeedbackTag.objects.filter(feedback=feedback).exclude(tag_id__in=tag_ids).delete()
        for tag in Tag.objects.filter(id__in=tag_ids):
            FeedbackTag.objects.get_or_create(feedback=feedback, tag=tag)
        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam, require_feature("inbox")])
    def summarize(self, request, pk=None):
        feedback = self.get_object()
        try:
            result = summarize_single_feedback(
                feedback,
                use_llm=bool(request.data.get("use_llm", True)),
            )
            return Response(
                {
                    **result,
                    "feedback": FeedbackDetailSerializer(feedback, context={"request": request}).data,
                }
            )
        except Exception as exc:
            logger.warning("AI summarization failed for feedback=%s: %s", feedback.id, exc)
            return Response(
                {"detail": f"Không thể kết nối AI Service tại {settings.AI_SERVICE_URL}: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam, require_feature("inbox")])
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

        return Response(FeedbackDetailSerializer(feedback, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam, require_feature("inbox")])
    def unmark_duplicate(self, request, pk=None):
        feedback = self.get_object()
        feedback.duplicate_of = None
        feedback.similarity_score = None
        feedback.is_duplicate_confirmed = False
        if feedback.status == Feedback.STATUS_DUPLICATE:
            feedback.status = Feedback.STATUS_NEW
        feedback.save()
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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, require_feature("inbox", "kanban")])
    def reply(self, request, pk=None):
        feedback = self.get_object()
        try:
            reply_obj = send_feedback_reply(
                feedback,
                request.user,
                request.data.get("message", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            FeedbackReplySerializer(reply_obj, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam, require_feature("inbox")])
    def similar(self, request, pk=None):
        feedback = self.get_object()
        try:
            data = find_similar_feedbacks(
                feedback,
                top_k=int(request.query_params.get("top_k", 6)),
                min_similarity=float(request.query_params.get("min_similarity", 0.35)),
            )
            return Response(data)
        except Exception as exc:
            logger.warning("AI similarity search failed: %s", exc)
            return Response(
                {"detail": f"Không thể kết nối AI Service tại {settings.AI_SERVICE_URL}: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class MultiSourceIngestView(APIView):
    """
    Simulated multi-source feedback ingestion endpoint (Web Form, Email, Live Chat, Community)
    for authenticated team members / portal demos.
    """

    permission_classes = [permissions.IsAuthenticated, require_feature("sources")]

    def post(self, request):
        serializer = MultiSourceIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source = FeedbackSource.objects.filter(code=data["source_code"], is_active=True).first()
        if not source:
            return Response(
                {"detail": f"Nguồn phản hồi {data['source_code']} không tồn tại hoặc đang tắt."},
                status=status.HTTP_400_BAD_REQUEST,
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

        sender_name = (data.get("sender_name") or "").strip() or request.user.display_name()
        sender_email = (data.get("sender_email") or "").strip() or request.user.email
        matched_author = User.objects.filter(email__iexact=sender_email).first() or request.user

        feedback = Feedback.objects.create(
            title=data["title"].strip(),
            content=data["content"].strip(),
            sender_name=sender_name,
            sender_email=sender_email,
            author=matched_author,
            product=product,
            source=source,
            impact_level=data["impact_level"],
            status=Feedback.STATUS_NEW,
        )

        for tag in Tag.objects.filter(id__in=data.get("tag_ids", [])):
            FeedbackTag.objects.get_or_create(feedback=feedback, tag=tag)

        notify_feedback_received(feedback, actor=request.user)

        return Response(
            FeedbackDetailSerializer(feedback, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, require_feature("dashboard")]

    def get(self, request):
        product_id = request.query_params.get("product")
        days = int(request.query_params.get("days", 30))
        return Response(build_dashboard_data(request.user, product_id=product_id, days=days))
