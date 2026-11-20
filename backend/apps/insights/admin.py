from django.contrib import admin

from .models import InsightFeedback, InsightGroup


@admin.register(InsightGroup)
class InsightGroupAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "priority_score",
        "priority_level",
        "status",
        "verification_status",
        "feedback_count",
    )
    list_filter = ("priority_level", "status", "verification_status", "product")


@admin.register(InsightFeedback)
class InsightFeedbackAdmin(admin.ModelAdmin):
    list_display = ("insight_group", "feedback", "similarity_to_centroid")
