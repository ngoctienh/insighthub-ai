from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_ok = False
    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "service": "insighthub-backend",
            "database": "connected" if db_ok else "error",
        },
        status=200 if db_ok else 503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.feedbacks.urls")),
    path("api/", include("apps.insights.urls")),
    path("api/", include("apps.roadmap.urls")),
    path("api/", include("apps.notifications.urls")),
    path("", include("apps.web.urls")),
]
