from django.contrib import admin

from .models import Notification, Vote


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("user", "feedback", "insight_group")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "event_type", "title", "is_read", "created_at")
