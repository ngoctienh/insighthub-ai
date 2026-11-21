import logging

from django.conf import settings
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsInternalTeam, IsPMOrAdmin, require_feature
from apps.feedbacks.models import Feedback, Product
from apps.feedbacks.serializers import FeedbackListSerializer
from apps.notifications.models import Vote
from apps.notifications.services import notify_insight_confirmed
from .models import InsightFeedback, InsightGroup
from .serializers import (
    InsightGroupDetailSerializer,
    InsightGroupListSerializer,
    InsightGroupWriteSerializer,
    RunAIPipelineSerializer,
)
from .services import (
    broadcast_insight_reply,
    classify_priority_level,
    execute_ai_pipeline,
    get_ai_task_status,
    get_duplicate_candidates_list,
    get_scoped_insights,
    get_unassigned_feedbacks_queryset,
    merge_insights,
    move_insight_kanban,
    regenerate_insight_reply,
    rescore_and_summarize_insight,
    split_insight,
)
from .tasks import run_ai_pipeline_task

logger = logging.getLogger(__name__)


class InsightGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, require_feature("insights")]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "vote"):
            return [permissions.IsAuthenticated(), require_feature("insights", "kanban", "roadmap")()]
        return super().get_permissions()

    def get_queryset(self):
        qs = get_scoped_insights(self.request.user)
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
        insight = serializer.save(verification_status=InsightGroup.VERIFY_CONFIRMED)
        for fb in Feedback.objects.filter(id__in=feedback_ids):
            InsightFeedback.objects.get_or_create(
                insight_group=insight,
                feedback=fb,
            )
        if feedback_ids:
            rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
        else:
            insight.sync_counts()

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
        if "priority_score" in request.data and "priority_level" not in request.data:
            updated.priority_level = classify_priority_level(updated.priority_score)
            updated.save(update_fields=["priority_level"])
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
        insight.verification_status = InsightGroup.VERIFY_CONFIRMED
        if insight.status == InsightGroup.STATUS_NEW:
            insight.status = InsightGroup.STATUS_REVIEWING
        insight.save(update_fields=["verification_status", "status"])
        notify_insight_confirmed(insight, actor=request.user)
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def reject(self, request, pk=None):
        insight = self.get_object()
        insight.verification_status = InsightGroup.VERIFY_REJECTED
        insight.save(update_fields=["verification_status"])
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsPMOrAdmin])
    def add_feedbacks(self, request, pk=None):
        insight = self.get_object()
        feedback_ids = request.data.get("feedback_ids", [])
        if not isinstance(feedback_ids, list) or not feedback_ids:
            return Response({"detail": "Cần danh sách feedback_ids."}, status=status.HTTP_400_BAD_REQUEST)

        for fb in Feedback.objects.filter(id__in=feedback_ids):
            InsightFeedback.objects.get_or_create(
                insight_group=insight,
                feedback=fb,
            )
        rescore_and_summarize_insight(insight, use_llm=False, preserve_title=True)
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

        merge_insights(target, source)
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

        new_group = split_insight(source, links, new_title)
        return Response(
            {
                "source_insight": InsightGroupDetailSerializer(source, context={"request": request}).data,
                "new_insight": InsightGroupDetailSerializer(new_group, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, require_feature("kanban")])
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

        update_assignee = "assigned_to" in request.data and role in (Role.ADMIN, Role.PRODUCT_MANAGER)
        assignee = None
        if update_assignee:
            assignee_id = request.data.get("assigned_to")
            assignee = User.objects.filter(id=assignee_id, is_active=True).first() if assignee_id else None

        move_insight_kanban(
            insight,
            actor=request.user,
            new_status=new_status,
            assignee=assignee,
            update_assignee=update_assignee,
        )
        return Response(InsightGroupDetailSerializer(insight, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def regenerate_reply(self, request, pk=None):
        insight = self.get_object()
        tone = request.data.get("tone", "empathetic")
        try:
            payload = regenerate_insight_reply(
                insight,
                tone=tone,
                use_llm=bool(request.data.get("use_llm", True)),
            )
            return Response(payload)
        except Exception as exc:
            logger.warning("Failed to regenerate draft reply for insight=%s: %s", insight.id, exc)
            return Response(
                {"detail": f"Không thể gọi AI Service để tạo nháp phản hồi: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsInternalTeam])
    def send_reply(self, request, pk=None):
        insight = self.get_object()
        message = request.data.get("message", "") or insight.draft_customer_reply
        try:
            stats = broadcast_insight_reply(insight, request.user, message, save_draft=True)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                **stats,
                "draft_customer_reply": insight.draft_customer_reply,
            },
            status=status.HTTP_201_CREATED,
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


class RunAIPipelineView(APIView):
    permission_classes = [permissions.IsAuthenticated, require_feature("ai_run")]

    def post(self, request):
        serializer = RunAIPipelineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cfg = serializer.validated_data

        product_id = cfg.get("product_id")
        if product_id and not Product.objects.filter(id=product_id).exists():
            return Response({"detail": "Sản phẩm không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        pipeline_cfg = {
            "similarity_threshold": cfg["similarity_threshold"],
            "eps": cfg["eps"],
            "min_samples": cfg["min_samples"],
            "use_llm": cfg["use_llm"],
            "include_clustered": cfg["include_clustered"],
        }

        if settings.CELERY_ENABLED:
            task = run_ai_pipeline_task.delay(config=pipeline_cfg, product_id=product_id)
            return Response(
                {"status": "QUEUED", "task_id": str(task.id)},
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            result = execute_ai_pipeline(config=pipeline_cfg, product_id=product_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("AI pipeline execution failed: %s", exc)
            return Response(
                {"detail": f"Lỗi khi gọi AI Service tại {settings.AI_SERVICE_URL}: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class AITaskStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, require_feature("ai_run", "insights")]

    def get(self, request, task_id: str):
        return Response(get_ai_task_status(task_id))


class DuplicateCandidatesView(APIView):
    """Return unconfirmed duplicate suggestions stored directly on Feedback records."""

    permission_classes = [permissions.IsAuthenticated, require_feature("insights")]

    def get(self, request):
        product_id = request.query_params.get("product")
        return Response(get_duplicate_candidates_list(product_id=product_id))


class UnassignedFeedbacksView(APIView):
    permission_classes = [permissions.IsAuthenticated, require_feature("insights")]

    def get(self, request):
        product_id = request.query_params.get("product")
        qs = get_unassigned_feedbacks_queryset(product_id=product_id)
        return Response(FeedbackListSerializer(qs[:100], many=True, context={"request": request}).data)
