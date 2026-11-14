from django.contrib import admin

from .models import AIAnalysisJob, InsightFeedback, InsightGroup


@admin.register(InsightGroup)
class InsightGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "priority_score", "priority_level", "status", "verification_status", "feedback_count")
    list_filter = ("priority_level", "status", "verification_status", "product")


@admin.register(InsightFeedback)
class InsightFeedbackAdmin(admin.ModelAdmin):
    list_display = ("insight_group", "feedback", "similarity_to_centroid", "added_by_ai")


@admin.register(AIAnalysisJob)
class AIAnalysisJobAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "status", "analysis_mode", "triggered_by", "created_at")
