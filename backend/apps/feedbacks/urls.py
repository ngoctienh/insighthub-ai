from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardView,
    FeedbackSourceViewSet,
    FeedbackViewSet,
    MultiSourceIngestView,
    ProductViewSet,
    TagViewSet,
)

router = DefaultRouter()
router.register("products", ProductViewSet, basename="products")
router.register("sources", FeedbackSourceViewSet, basename="sources")
router.register("tags", TagViewSet, basename="tags")
router.register("feedbacks", FeedbackViewSet, basename="feedbacks")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("sources/ingest/", MultiSourceIngestView.as_view(), name="sources-ingest"),
    path("", include(router.urls)),
]
