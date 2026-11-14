from django.contrib import admin

from .models import ActivityLog, Comment, Notification, Vote


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("user", "feedback", "insight_group", "created_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "feedback", "insight_group", "is_internal", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "event_type", "title", "is_read", "created_at")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "action", "actor", "created_at")
