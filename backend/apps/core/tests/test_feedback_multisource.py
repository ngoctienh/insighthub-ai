import os
import pytest

from apps.feedbacks.models import Feedback


DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_multi_source_ingest_simulator(api_client, seeded_db):
    # Unauthenticated ingest blocked -> 401
    unauth = api_client.post(
        "/api/sources/ingest/",
        {
            "source_code": "EMAIL",
            "title": "Lỗi test",
            "content": "Nội dung test",
        },
        format="json",
    )
    assert unauth.status_code == 401

    # Authenticated Customer Support / PM simulator ingestion across 4 sources
    cs_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "cs_linh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {cs_login['access']}")

    for src_code in ("WEB_FORM", "EMAIL", "LIVE_CHAT", "COMMUNITY"):
        resp = api_client.post(
            "/api/sources/ingest/",
            {
                "source_code": src_code,
                "title": f"Phản hồi mô phỏng từ {src_code}",
                "content": "Nội dung kiểm thử đa nguồn lưu chung bảng feedbacks.",
                "sender_name": "Khách mô phỏng",
                "sender_email": "sim@example.com",
                "impact_level": "HIGH",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["source_code"] == src_code

    assert Feedback.objects.filter(source__code__in=["WEB_FORM", "EMAIL", "LIVE_CHAT", "COMMUNITY"]).count() >= 58


@pytest.mark.django_db
def test_dashboard_metrics_and_feedback_operations(api_client, seeded_db):
    pm_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "pm_minh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {pm_login['access']}")

    dash = api_client.get("/api/dashboard/").json()
    assert dash["kpis"]["total_feedbacks"] == Feedback.objects.count()
    assert len(dash["feedbacks_by_source"]) == 4
    assert len(dash["feedbacks_by_status"]) == 5
    assert len(dash["feedbacks_by_tag"]) >= 1
    assert len(dash["top_5_issues"]) == 5

    # Filtering & search
    filtered = api_client.get("/api/feedbacks/?source=EMAIL&search=MoMo").json()["results"]
    assert len(filtered) >= 1
    assert any("MoMo" in item["title"] for item in filtered)
