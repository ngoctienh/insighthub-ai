import os
import pytest

from apps.feedbacks.models import Feedback
from apps.insights.models import InsightGroup
from apps.notifications.models import Notification


DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_kanban_workflow_public_private_roadmap_and_notifications(api_client, seeded_db):
    pm_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "pm_minh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {pm_login['access']}")

    insight = InsightGroup.objects.filter(status="NEW").first()
    assert insight is not None

    # Move insight on Kanban to PLANNED
    move_resp = api_client.post(
        f"/api/insights/{insight.id}/move_kanban/",
        {"status": "PLANNED"},
        format="json",
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["status"] == "PLANNED"

    # Update single feedback status directly (Kanban for Feedbacks)
    fb = Feedback.objects.filter(status="NEW").first()
    assert fb is not None
    fb_move = api_client.patch(f"/api/feedbacks/{fb.id}/", {"status": "REVIEWING"}, format="json")
    assert fb_move.status_code == 200
    assert fb_move.json()["status"] == "REVIEWING"

    # Create Public Roadmap item linked to insight
    rm_resp = api_client.post(
        "/api/roadmap/",
        {
            "product": insight.product_id,
            "title": "Cải thiện bản đồ GPS và tìm kiếm tiếng Việt",
            "description": "Cập nhật tìm kiếm không dấu và lưu ghi chú cổng giao.",
            "public_description": "Tìm kiếm món nhanh hơn và ghim địa chỉ giao hàng chính xác.",
            "status": "PLANNED",
            "visibility": "PUBLIC",
            "quarter": "Q1 2027",
            "progress_percent": 20,
            "insight_group_ids": [insight.id],
        },
        format="json",
    )
    assert rm_resp.status_code == 201

    # Public roadmap accessible anonymously and NEVER leaks PRIVATE items
    api_client.credentials()  # anonymous
    pub_resp = api_client.get("/api/roadmap/public/")
    assert pub_resp.status_code == 200
    pub_items = pub_resp.json()
    assert len(pub_items) >= 4
    for item in pub_items:
        assert "Tái cấu trúc Search Index" not in item["title"]  # Private item hidden

    # Customer notifications strictly scoped to their own notifications
    cust_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "customer_an", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {cust_login['access']}")

    notifs = api_client.get("/api/notifications/").json()["results"]
    assert len(notifs) >= 1
    assert all("link_url" in n for n in notifs)
    other_user_notifs = Notification.objects.exclude(recipient__username="customer_an")
    if other_user_notifs.exists():
        other_id = other_user_notifs.first().id
        assert api_client.post(f"/api/notifications/{other_id}/mark_read/").status_code == 404
