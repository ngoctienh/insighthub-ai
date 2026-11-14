from django.db.models import Q
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsInternalTeam
from apps.notifications.models import ActivityLog, Comment
from apps.notifications.serializers import CommentSerializer
from apps.notifications.services import log_activity, notify_roadmap_updated
from .models import RoadmapItem
from .serializers import PublicRoadmapItemSerializer, RoadmapItemSerializer


class PublicRoadmapListView(generics.ListAPIView):
    """
    Public roadmap accessible to customers and guests.
    Strictly filters visibility=PUBLIC and status in (PLANNED, IN_PROGRESS, COMPLETED).
    """

    serializer_class = PublicRoadmapItemSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        qs = (
            RoadmapItem.objects.select_related("product")
            .prefetch_related("insight_groups")
            .filter(
                visibility=RoadmapItem.VISIBILITY_PUBLIC,
                status__in=[
                    RoadmapItem.STATUS_PLANNED,
                    RoadmapItem.STATUS_IN_PROGRESS,
                    RoadmapItem.STATUS_COMPLETED,
                ],
            )
        )
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("status", "-updated_at")


class RoadmapItemViewSet(viewsets.ModelViewSet):
    serializer_class = RoadmapItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsInternalTeam]
    pagination_class = None

    def get_queryset(self):
        qs = (
            RoadmapItem.objects.select_related("product", "owner", "owner__role", "created_by")
            .prefetch_related("insight_groups")
            .all()
        )
        params = self.request.query_params
        if params.get("visibility"):
            qs = qs.filter(visibility=params["visibility"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("product"):
            qs = qs.filter(product_id=params["product"])
        if params.get("quarter"):
            qs = qs.filter(quarter__icontains=params["quarter"])
        if params.get("search"):
            s = params["search"].strip()
            qs = qs.filter(Q(code__icontains=s) | Q(title__icontains=s) | Q(description__icontains=s))
        return qs

    def _require_pm_or_admin(self, request):
        if request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER):
            return Response(
                {"detail": "Chỉ Product Manager hoặc Admin mới có quyền chỉnh sửa Roadmap."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def create(self, request, *args, **kwargs):
        denied = self._require_pm_or_admin(request)
        if denied:
            return denied
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        log_activity(
            request.user,
            ActivityLog.ENTITY_ROADMAP,
            item.id,
            "CREATED",
            f"Tạo roadmap item {item.code}: {item.title} ({item.visibility})",
        )
        notify_roadmap_updated(item, actor=request.user, created=True)
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        denied = self._require_pm_or_admin(request)
        if denied:
            return denied
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        old_status = instance.status
        old_progress = instance.progress_percent

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        log_activity(
            request.user,
            ActivityLog.ENTITY_ROADMAP,
            updated.id,
            "UPDATED",
            f"Cập nhật roadmap {updated.code}: {old_status} ({old_progress}%) → {updated.status} ({updated.progress_percent}%)",
            old_value={"status": old_status, "progress": old_progress},
            new_value={"status": updated.status, "progress": updated.progress_percent},
        )
        notify_roadmap_updated(updated, actor=request.user, created=False)
        return Response(self.get_serializer(updated).data)

    def destroy(self, request, *args, **kwargs):
        denied = self._require_pm_or_admin(request)
        if denied:
            return denied
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        item = self.get_object()
        if request.method == "GET":
            qs = item.comments.select_related("author", "author__role").all()
            return Response(CommentSerializer(qs, many=True).data)

        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"detail": "Nội dung bình luận không được để trống."}, status=status.HTTP_400_BAD_REQUEST)
        comment = Comment.objects.create(
            author=request.user,
            roadmap_item=item,
            content=content,
            is_internal=True,
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
