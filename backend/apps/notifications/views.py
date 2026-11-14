from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsInternalTeam
from .models import ActivityLog, Notification
from .serializers import ActivityLogSerializer, NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Strictly scoped to the authenticated user.
        # Customers never receive internal notifications belonging to other users.
        qs = Notification.objects.select_related("actor").filter(recipient=self.request.user)
        unread_only = self.request.query_params.get("unread_only")
        if unread_only in ("1", "true", "True"):
            qs = qs.filter(is_read=False)
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        return Response({"marked_read": updated}, status=status.HTTP_200_OK)


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsInternalTeam]

    def get_queryset(self):
        qs = ActivityLog.objects.select_related("actor").all()
        entity_type = self.request.query_params.get("entity_type")
        entity_id = self.request.query_params.get("entity_id")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if self.request.user.role_code not in (Role.ADMIN, Role.PRODUCT_MANAGER):
            qs = qs[:100]
        return qs
