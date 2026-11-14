from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActivityLogViewSet, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("activity-logs", ActivityLogViewSet, basename="activity-logs")

urlpatterns = [
    path("", include(router.urls)),
]
