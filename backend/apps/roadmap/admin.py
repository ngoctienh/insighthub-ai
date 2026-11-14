from django.contrib import admin

from .models import RoadmapItem, RoadmapItemInsight


@admin.register(RoadmapItem)
class RoadmapItemAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "status", "visibility", "quarter", "progress_percent", "owner")
    list_filter = ("status", "visibility", "quarter", "product")


@admin.register(RoadmapItemInsight)
class RoadmapItemInsightAdmin(admin.ModelAdmin):
    list_display = ("roadmap_item", "insight_group", "created_at")
