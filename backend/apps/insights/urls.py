from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AIJobViewSet, InsightGroupViewSet, RunAIPipelineView, UnassignedFeedbacksView

router = DefaultRouter()
router.register("insights", InsightGroupViewSet, basename="insights")
router.register("ai/jobs", AIJobViewSet, basename="ai-jobs")

urlpatterns = [
    path("ai/analyze/", RunAIPipelineView.as_view(), name="ai-analyze"),
    path("ai/unassigned/", UnassignedFeedbacksView.as_view(), name="ai-unassigned"),
    path("", include(router.urls)),
]
