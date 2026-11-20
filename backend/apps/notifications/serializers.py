from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    link_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "title",
            "message",
            "feedback",
            "link_url",
            "is_read",
            "created_at",
        ]

    def get_link_url(self, obj: Notification) -> str:
        if obj.feedback_id:
            return f"/inbox/{obj.feedback_id}"
        if obj.event_type == Notification.EVENT_ROADMAP_UPDATED:
            return "/public-roadmap"
        if obj.event_type in (Notification.EVENT_INSIGHT_CONFIRMED, Notification.EVENT_STATUS_CHANGED):
            return "/insights"
        return ""
