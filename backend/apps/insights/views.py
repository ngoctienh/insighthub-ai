import logging

import httpx
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsInternalTeam, IsPMOrAdmin
from apps.feedbacks.models import Feedback, Product
from apps.feedbacks.serializers import FeedbackListSerializer
from apps.notifications.models import ActivityLog, Comment, Vote
from apps.notifications.serializers import ActivityLogSerializer, CommentSerializer
from apps.notifications.services import (
    log_activity,
    notify_insight_confirmed,
    notify_insight_status_changed,
)
from .models import AIAnalysisJob, InsightFeedback, InsightGroup
from .serializers import (
    AIAnalysisJobSerializer,
    InsightGroupDetailSerializer,
    InsightGroupListSerializer,
    InsightGroupWriteSerializer,
    RunAIPipelineSerializer,
)
from .services import (
    _ai_headers,
    classify_priority_level,
    execute_ai_pipeline,
    rescore_and_summarize_insight,
)
from .tasks import run_ai_pipeline_task

logger = logging.getLogger(__name__)


class InsightGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsInternalTeam]

    def get_queryset(self):
        user = self.request.user
        role = user.role_code
        qs = (
            InsightGroup.objects.select_related("product", "assigned_to", "assigned_to__role", "created_by")
            .prefetch_related("insight_feedback_links__feedback__source", "roadmap_items")
        )

        if role == Role.DEVELOPER:
            qs = qs.filter(
                Q(assigned_to=user) | Q(verification_status=InsightGroup.VERIFY_CONFIRMED)
            ).distinct()
        elif role == Role.CUSTOMER_SUPPORT:
            qs = qs.filter(
                Q(assigned_to=user) | Q(verification_status=InsightGroup.VERIFY_CONFIRMED)
            ).distinct()

        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("verification_status"):
            qs = qs.filter(verification_status=params["verification_status"])
        if params.get("priority_level"):
            qs = qs.filter(priority_level=params["priority_level"])
        if params.get("product"):
            qs = qs.filter(product_id=params["product"])
        if params.get("assigned_to"):
            qs = qs.filter(assigned_to_id=params["assigned_to"])
        if params.get("search"):
            s = params["search"].strip()
            qs = qs.filter(Q(code__icontains=s) | Q(title__icontains=s) | Q(description__icontains=s))

        if params.get("exclude_rejected") in ("1", "true", "True"):
            qs = qs.exclude(verification_status=InsightGroup.VERIFY_REJECTED)

        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return InsightGroupWriteSerializer
        if self.action == "retrieve":
            return InsightGroupDetailSerializer
        return InsightGroupListSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER):
            return Response(
                {"detail": "Chỉ PM hoặc Admin mới có quyền tạo nhóm insight mới."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback_ids = serializer.validated_data.pop("feedback_ids", [])
        insight = serializer.save(
            created_by=request.user,
            verification_status=InsightGroup.VERIFY_CONFIRMED,
            analysis_mode="manual",
        )
        for fb in Feedback.objects.filter(id__in=feedback_ids):
            InsightFeedback.objects.get_or_create(
                insight_group=insight,
                feedback=fb,
                defaults={"added_by_ai": False, "added_by": request.user},
            )
        if feedback_ids:
            rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
        else:
            insight.sync_counts()

        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            insight.id,
            "CREATED",
            f"Tạo nhóm insight thủ công {insight.code}: {insight.title}",
        )
        return Response(
            InsightGroupDetailSerializer(insight, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        if request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER):
            return Response(
                {"detail": "Chỉ PM hoặc Admin mới có quyền chỉnh sửa cấu trúc nhóm insight."},
                status=status.HTTP_403_FORBIDDEN,
            )
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("feedback_ids", None)
        updated = serializer.save()
        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            updated.id,
            "UPDATED",
            f"Cập nhật thông tin nhóm insight {updated.code}",
        )
        return Response(InsightGroupDetailSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        if request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER):
            return Response(
                {"detail": "Chỉ PM hoặc Admin mới có quyền xóa nhóm insight."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def confirm(self, request, pk=None):
        insight = self.get_object()
        old_val = insight.verification_status
        insight.verification_status = InsightGroup.VERIFY_CONFIRMED
        if insight.status == InsightGroup.STATUS_NEW:
            insight.status = InsightGroup.STATUS_ANALYZING
        insight.save(update_fields=["verification_status", "status", "updated_at"])
        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            insight.id,
            "CONFIRMED",
            f"Xác nhận nhóm insight {insight.code}",
            old_value={"verification_status": old_val},
            new_value={"verification_status": insight.verification_status},
        )
        notify_insight_confirmed(insight, actor=request.user)
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def reject(self, request, pk=None):
        insight = self.get_object()
        old_val = insight.verification_status
        insight.verification_status = InsightGroup.VERIFY_REJECTED
        insight.save(update_fields=["verification_status", "updated_at"])
        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            insight.id,
            "REJECTED",
            f"Từ chối nhóm insight {insight.code}",
            old_value={"verification_status": old_val},
            new_value={"verification_status": insight.verification_status},
        )
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def override_priority(self, request, pk=None):
        insight = self.get_object()
        old_score = insight.priority_score
        old_level = insight.priority_level

        new_score = request.data.get("priority_score")
        new_level = request.data.get("priority_level")
        notes = (request.data.get("pm_priority_notes") or "").strip()

        if new_score is not None:
            score_val = max(0.0, min(100.0, float(new_score)))
            insight.priority_score = round(score_val, 1)
            insight.priority_level = new_level or classify_priority_level(score_val)
        elif new_level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            insight.priority_level = new_level
        else:
            return Response(
                {"detail": "Vui lòng cung cấp priority_score (0-100) hoặc priority_level hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        insight.is_priority_overridden = True
        insight.pm_priority_notes = notes
        insight.save(
            update_fields=[
                "priority_score",
                "priority_level",
                "is_priority_overridden",
                "pm_priority_notes",
                "updated_at",
            ]
        )
        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            insight.id,
            "PRIORITY_OVERRIDDEN",
            f"PM điều chỉnh ưu tiên {insight.code}: {old_score} ({old_level}) → {insight.priority_score} ({insight.priority_level})",
            old_value={"priority_score": old_score, "priority_level": old_level},
            new_value={"priority_score": insight.priority_score, "priority_level": insight.priority_level, "notes": notes},
        )
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def add_feedbacks(self, request, pk=None):
        insight = self.get_object()
        feedback_ids = request.data.get("feedback_ids", [])
        if not isinstance(feedback_ids, list) or not feedback_ids:
            return Response({"detail": "Cần danh sách feedback_ids."}, status=status.HTTP_400_BAD_REQUEST)

        added = 0
        for fb in Feedback.objects.filter(id__in=feedback_ids):
            _, created = InsightFeedback.objects.get_or_create(
                insight_group=insight,
                feedback=fb,
                defaults={"added_by_ai": False, "added_by": request.user},
            )
            if created:
                added += 1
        rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            insight.id,
            "FEEDBACKS_ADDED",
            f"Thêm {added} feedback vào {insight.code}",
        )
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def remove_feedback(self, request, pk=None):
        insight = self.get_object()
        feedback_id = request.data.get("feedback_id")
        deleted, _ = InsightFeedback.objects.filter(
            insight_group=insight,
            feedback_id=feedback_id,
        ).delete()
        if not deleted:
            return Response({"detail": "Feedback không nằm trong nhóm này."}, status=status.HTTP_404_NOT_FOUND)
        rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            insight.id,
            "FEEDBACK_REMOVED",
            f"Gỡ feedback #{feedback_id} khỏi {insight.code}",
        )
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def merge(self, request, pk=None):
        target = self.get_object()
        source_id = request.data.get("source_insight_id")
        if not source_id or int(source_id) == target.id:
            return Response({"detail": "Cần chọn nhóm insight nguồn khác nhóm hiện tại."}, status=status.HTTP_400_BAD_REQUEST)
        source = InsightGroup.objects.filter(id=source_id).first()
        if not source:
            return Response({"detail": "Nhóm insight nguồn không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            for link in source.insight_feedback_links.all():
                InsightFeedback.objects.get_or_create(
                    insight_group=target,
                    feedback=link.feedback,
                    defaults={
                        "similarity_to_centroid": link.similarity_to_centroid,
                        "added_by_ai": False,
                        "added_by": request.user,
                    },
                )
            source_code = source.code
            source.delete()
            rescore_and_summarize_insight(target, use_llm=False, preserve_title=True)

        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            target.id,
            "MERGED",
            f"Gộp nhóm {source_code} vào {target.code}",
        )
        return Response(InsightGroupDetailSerializer(target, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def split(self, request, pk=None):
        source = self.get_object()
        feedback_ids = request.data.get("feedback_ids", [])
        new_title = (request.data.get("new_title") or "").strip() or f"Nhóm tách từ {source.code}"

        if not isinstance(feedback_ids, list) or not feedback_ids:
            return Response({"detail": "Cần chọn ít nhất 1 feedback để tách nhóm."}, status=status.HTTP_400_BAD_REQUEST)

        links = list(
            InsightFeedback.objects.filter(insight_group=source, feedback_id__in=feedback_ids)
        )
        if not links:
            return Response({"detail": "Không tìm thấy feedback đã chọn trong nhóm này."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            new_group = InsightGroup.objects.create(
                product=source.product,
                title=new_title[:255],
                status=InsightGroup.STATUS_NEW,
                verification_status=InsightGroup.VERIFY_CONFIRMED,
                created_by=request.user,
                analysis_mode="manual_split",
            )
            for link in links:
                InsightFeedback.objects.create(
                    insight_group=new_group,
                    feedback=link.feedback,
                    added_by_ai=False,
                    added_by=request.user,
                )
                link.delete()

            rescore_and_summarize_insight(source, use_llm=False, preserve_title=True)
            rescore_and_summarize_insight(new_group, use_llm=False, preserve_title=True)

        log_activity(
            request.user,
            ActivityLog.ENTITY_INSIGHT,
            source.id,
            "SPLIT",
            f"Tách {len(links)} feedback từ {source.code} sang nhóm mới {new_group.code}",
        )
        return Response(
            {
                "source_insight": InsightGroupDetailSerializer(source, context={"request": request}).data,
                "new_insight": InsightGroupDetailSerializer(new_group, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def move_kanban(self, request, pk=None):
        insight = self.get_object()
        role = request.user.role_code

        if role not in (Role.ADMIN, Role.PRODUCT_MANAGER):
            if insight.assigned_to_id != request.user.id:
                return Response(
                    {"detail": "Bạn chỉ có thể cập nhật Kanban cho insight được phân công cho mình."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        new_status = request.data.get("status")
        valid_statuses = {c[0] for c in InsightGroup.STATUS_CHOICES}
        if new_status and new_status not in valid_statuses:
            return Response({"detail": "Trạng thái Kanban không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        old_status = insight.status
        changes = []
        if new_status and new_status != old_status:
            insight.status = new_status
            changes.append(f"trạng thái {old_status} → {new_status}")

        if "assigned_to" in request.data and role in (Role.ADMIN, Role.PRODUCT_MANAGER):
            assignee_id = request.data.get("assigned_to")
            assignee = User.objects.filter(id=assignee_id, is_active=True).first() if assignee_id else None
            insight.assigned_to = assignee
            changes.append(f"phụ trách: {assignee.display_name() if assignee else 'Chưa gán'}")

        if "due_date" in request.data and role in (Role.ADMIN, Role.PRODUCT_MANAGER):
            insight.due_date = request.data.get("due_date") or None
            changes.append(f"hạn xử lý: {insight.due_date}")

        insight.save()

        # Sync status on linked feedbacks when insight progresses to PLANNED / IN_PROGRESS / COMPLETED
        if new_status in (
            InsightGroup.STATUS_PLANNED,
            InsightGroup.STATUS_IN_PROGRESS,
            InsightGroup.STATUS_COMPLETED,
        ):
            Feedback.objects.filter(
                insight_links__insight_group=insight,
                is_duplicate_confirmed=False,
            ).update(status=new_status)

        if changes:
            log_activity(
                request.user,
                ActivityLog.ENTITY_INSIGHT,
                insight.id,
                "KANBAN_UPDATED",
                f"Cập nhật Kanban {insight.code}: {', '.join(changes)}",
                old_value={"status": old_status},
                new_value={"status": insight.status},
            )
            if new_status and new_status != old_status:
                notify_insight_status_changed(insight, old_status, new_status, actor=request.user)

        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def regenerate_reply(self, request, pk=None):
        insight = self.get_object()
        tone = request.data.get("tone", "empathetic")
        samples = [
            f"{link.feedback.title}: {link.feedback.content}"
            for link in insight.insight_feedback_links.select_related("feedback").all()[:5]
        ]
        try:
            with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
                resp = client.post(
                    f"{settings.AI_SERVICE_URL}/draft-reply",
                    json={
                        "insight_title": insight.title,
                        "insight_summary": insight.description,
                        "sample_feedbacks": samples,
                        "tone": tone,
                        "use_llm": bool(request.data.get("use_llm", True)),
                    },
                    headers=_ai_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
            insight.draft_customer_reply = data["draft_reply"]
            insight.save(update_fields=["draft_customer_reply", "updated_at"])
            return Response(
                {
                    "draft_customer_reply": insight.draft_customer_reply,
                    "analysis_mode": data["analysis_mode"],
                    "tone": data["tone"],
                }
            )
        except Exception as exc:
            logger.warning("Failed to regenerate draft reply for insight=%s: %s", insight.id, exc)
            return Response(
                {"detail": f"Không thể gọi AI Service để tạo nháp phản hồi: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=True, methods=["post"])
    def vote(self, request, pk=None):
        insight = self.get_object()
        existing = Vote.objects.filter(user=request.user, insight_group=insight).first()
        if existing:
            existing.delete()
            voted = False
        else:
            Vote.objects.create(user=request.user, insight_group=insight)
            voted = True
        return Response({"voted": voted, "votes_count": insight.votes.count()})

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        insight = self.get_object()
        if request.method == "GET":
            qs = insight.comments.select_related("author", "author__role").all()
            return Response(CommentSerializer(qs, many=True).data)

        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"detail": "Nội dung bình luận không được để trống."}, status=status.HTTP_400_BAD_REQUEST)
        comment = Comment.objects.create(
            author=request.user,
            insight_group=insight,
            content=content,
            is_internal=True,
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        insight = self.get_object()
        logs = ActivityLog.objects.select_related("actor").filter(
            entity_type=ActivityLog.ENTITY_INSIGHT,
            entity_id=insight.id,
        )
        return Response(ActivityLogSerializer(logs, many=True).data)


class RunAIPipelineView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPMOrAdmin]

    def post(self, request):
        serializer = RunAIPipelineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cfg = serializer.validated_data

        product = None
        if cfg.get("product_id"):
            product = Product.objects.filter(id=cfg["product_id"]).first()
            if not product:
                return Response({"detail": "Sản phẩm không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        job = AIAnalysisJob.objects.create(
            product=product,
            triggered_by=request.user,
            status=AIAnalysisJob.STATUS_PENDING,
            config={
                "similarity_threshold": cfg["similarity_threshold"],
                "eps": cfg["eps"],
                "min_samples": cfg["min_samples"],
                "use_llm": cfg["use_llm"],
                "include_clustered": cfg["include_clustered"],
            },
        )

        if settings.CELERY_ENABLED:
            run_ai_pipeline_task.delay(job.id)
            return Response(AIAnalysisJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

        job = execute_ai_pipeline(job.id)
        http_status = (
            status.HTTP_200_OK
            if job.status == AIAnalysisJob.STATUS_COMPLETED
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(AIAnalysisJobSerializer(job).data, status=http_status)


class AIJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AIAnalysisJobSerializer
    permission_classes = [permissions.IsAuthenticated, IsInternalTeam]
    queryset = AIAnalysisJob.objects.select_related("product", "triggered_by").all()


class UnassignedFeedbacksView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsInternalTeam]

    def get(self, request):
        grouped_ids = InsightFeedback.objects.exclude(
            insight_group__verification_status=InsightGroup.VERIFY_REJECTED
        ).values_list("feedback_id", flat=True)
        qs = (
            Feedback.objects.select_related("product", "source", "assigned_to")
            .prefetch_related("tags", "insight_groups")
            .filter(is_duplicate_confirmed=False)
            .exclude(id__in=grouped_ids)
        )
        product_id = request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return Response(FeedbackListSerializer(qs[:100], many=True, context={"request": request}).data)
