from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PublicRoadmapListView, RoadmapItemViewSet

router = DefaultRouter()
router.register("roadmap", RoadmapItemViewSet, basename="roadmap")

urlpatterns = [
    path("roadmap/public/", PublicRoadmapListView.as_view(), name="roadmap-public"),
    path("", include(router.urls)),
]
