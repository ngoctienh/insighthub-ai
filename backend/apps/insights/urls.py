from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AITaskStatusView,
    DuplicateCandidatesView,
    InsightGroupViewSet,
    RunAIPipelineView,
    UnassignedFeedbacksView,
)

router = DefaultRouter()
router.register("insights", InsightGroupViewSet, basename="insights")

urlpatterns = [
    path("ai/analyze/", RunAIPipelineView.as_view(), name="ai-analyze"),
    path("ai/tasks/<str:task_id>/", AITaskStatusView.as_view(), name="ai-task-status"),
    path("ai/duplicates/", DuplicateCandidatesView.as_view(), name="ai-duplicates"),
    path("ai/unassigned/", UnassignedFeedbacksView.as_view(), name="ai-unassigned"),
    path("", include(router.urls)),
]
