from django.urls import path

from .views.auth_views import (
    landing_view,
    login_view,
    logout_view,
    register_view,
    settings_view,
    users_view,
)
from .views.feedback_views import (
    dashboard_view,
    feedback_detail_view,
    inbox_view,
    notifications_view,
    portal_view,
    sources_hub_view,
)
from .views.insight_kanban_views import (
    ai_task_status_view,
    insight_detail_view,
    insights_view,
    kanban_view,
)
from .views.roadmap_views import public_roadmap_view, roadmap_view

urlpatterns = [
    path("", landing_view, name="web-landing"),
    path("login/", login_view, name="web-login"),
    path("register/", register_view, name="web-register"),
    path("logout/", logout_view, name="web-logout"),
    path("public-roadmap/", public_roadmap_view, name="web-public-roadmap"),
    path("portal/", portal_view, name="web-portal"),
    path("dashboard/", dashboard_view, name="web-dashboard"),
    path("inbox/", inbox_view, name="web-inbox"),
    path("inbox/<int:pk>/", feedback_detail_view, name="web-feedback-detail"),
    path("sources/", sources_hub_view, name="web-sources"),
    path("insights/", insights_view, name="web-insights"),
    path("insights/ai-task/<str:task_id>/", ai_task_status_view, name="web-ai-task-status"),
    path("insights/<int:pk>/", insight_detail_view, name="web-insight-detail"),
    path("kanban/", kanban_view, name="web-kanban"),
    path("roadmap/", roadmap_view, name="web-roadmap"),
    path("notifications/", notifications_view, name="web-notifications"),
    path("users/", users_view, name="web-users"),
    path("settings/", settings_view, name="web-settings"),
]
