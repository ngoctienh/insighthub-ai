import os
import pytest

from apps.feedbacks.models import Feedback


DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_multi_source_ingest_and_webhook_security(api_client, seeded_db):
    # Unauthenticated without webhook token -> 401
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

    # Valid external webhook token -> 201 saved to unified feedbacks table
    webhook_ok = api_client.post(
        "/api/sources/ingest/",
        {
            "source_code": "EMAIL",
            "title": "Không nhận được email hóa đơn đơn hàng",
            "content": "Tôi đã đặt món thành công nhưng chưa thấy gửi hóa đơn về Gmail.",
            "sender_name": "Trần Văn Bình",
            "sender_email": "binh.tran@example.com",
            "impact_level": "MEDIUM",
            "external_reference_id": "msg-88123",
            "source_metadata": {"subject": "Hỗ trợ hóa đơn", "provider": "Gmail Webhook"},
        },
        HTTP_X_SOURCE_TOKEN="wh_email_bepviet_2026",
        format="json",
    )
    assert webhook_ok.status_code == 201
    assert webhook_ok.json()["source_code"] == "EMAIL"

    # Authenticated Live Chat & Community simulator ingestion
    cs_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "cs_linh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {cs_login['access']}")

    for src_code in ("LIVE_CHAT", "COMMUNITY", "WEB_FORM"):
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
    assert len(dash["top_5_issues"]) == 5

    # Filtering & duplicate check
    filtered = api_client.get("/api/feedbacks/?source=EMAIL&search=MoMo").json()["results"]
    assert len(filtered) >= 1
    assert any("MoMo" in item["title"] for item in filtered)
