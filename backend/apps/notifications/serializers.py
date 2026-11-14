from rest_framework import serializers

from apps.accounts.serializers import UserMinimalSerializer
from .models import ActivityLog, Comment, Notification


class CommentSerializer(serializers.ModelSerializer):
    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "feedback",
            "insight_group",
            "roadmap_item",
            "content",
            "is_internal",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "title",
            "message",
            "actor_name",
            "feedback",
            "insight_group",
            "roadmap_item",
            "link_url",
            "is_read",
            "created_at",
        ]

    def get_actor_name(self, obj: Notification) -> str:
        return obj.actor.display_name() if obj.actor_id else "InsightHub System"


class ActivityLogSerializer(serializers.ModelSerializer):
    actor = UserMinimalSerializer(read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "actor",
            "entity_type",
            "entity_id",
            "action",
            "old_value",
            "new_value",
            "description",
            "created_at",
        ]
