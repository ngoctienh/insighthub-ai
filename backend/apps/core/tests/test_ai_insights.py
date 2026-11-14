import os
import pytest

from apps.insights.models import InsightGroup


DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_ai_pipeline_clusters_unassigned_feedbacks_and_insight_management(
    api_client, seeded_db, bridge_real_ai_service
):
    pm_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "pm_minh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {pm_login['access']}")

    initial_count = InsightGroup.objects.count()
    unassigned_before = api_client.get("/api/ai/unassigned/").json()
    assert len(unassigned_before) == 12

    # Run real AI pipeline on the 12 unclustered feedbacks
    run_resp = api_client.post(
        "/api/ai/analyze/",
        {
            "similarity_threshold": 0.65,
            "eps": 0.62,
            "min_samples": 2,
            "use_llm": False,
            "include_clustered": False,
        },
        format="json",
    )
    assert run_resp.status_code == 200
    job = run_resp.json()
    assert job["status"] == "COMPLETED"
    assert job["metrics"]["processed_count"] == 12
    assert len(job["metrics"]["created_insight_ids"]) >= 2
    assert InsightGroup.objects.count() >= initial_count + 2

    new_insight_id = job["metrics"]["created_insight_ids"][0]
    detail = api_client.get(f"/api/insights/{new_insight_id}/").json()
    assert detail["priority_reasoning"]
    assert detail["draft_customer_reply"]

    # Confirm insight
    confirm_resp = api_client.post(f"/api/insights/{new_insight_id}/confirm/", {}, format="json")
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["verification_status"] == "CONFIRMED"

    # PM priority override
    override_resp = api_client.post(
        f"/api/insights/{new_insight_id}/override_priority/",
        {"priority_score": 94.5, "pm_priority_notes": "Ưu tiên cao do ảnh hưởng đăng nhập OTP"},
        format="json",
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["is_priority_overridden"] is True
    assert override_resp.json()["priority_level"] == "CRITICAL"

    # Regenerate draft customer reply
    reply_resp = api_client.post(
        f"/api/insights/{new_insight_id}/regenerate_reply/",
        {"tone": "update", "use_llm": False},
        format="json",
    )
    assert reply_resp.status_code == 200
    assert "roadmap" in reply_resp.json()["draft_customer_reply"].lower()

    # Similarity search on a feedback item
    first_unassigned_id = unassigned_before[0]["id"]
    sim_resp = api_client.get(f"/api/feedbacks/{first_unassigned_id}/similar/?min_similarity=0.1")
    assert sim_resp.status_code == 200
    assert len(sim_resp.json()["matches"]) >= 1
