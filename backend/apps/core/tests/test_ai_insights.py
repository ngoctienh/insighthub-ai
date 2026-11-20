import os
import pytest

from apps.insights.models import InsightGroup


DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_ai_pipeline_clusters_unassigned_feedbacks_and_single_summarize(
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
    result = run_resp.json()
    assert result["status"] == "COMPLETED"
    assert result["metrics"]["processed_count"] == 12
    assert len(result["metrics"]["created_insight_ids"]) >= 2
    assert InsightGroup.objects.count() >= initial_count + 2

    new_insight_id = result["metrics"]["created_insight_ids"][0]
    detail = api_client.get(f"/api/insights/{new_insight_id}/").json()
    assert detail["priority_reasoning"]
    assert detail["draft_customer_reply"]

    # Confirm insight
    confirm_resp = api_client.post(f"/api/insights/{new_insight_id}/confirm/", {}, format="json")
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["verification_status"] == "CONFIRMED"

    # Regenerate draft customer reply
    reply_resp = api_client.post(
        f"/api/insights/{new_insight_id}/regenerate_reply/",
        {"tone": "update", "use_llm": False},
        format="json",
    )
    assert reply_resp.status_code == 200
    assert "roadmap" in reply_resp.json()["draft_customer_reply"].lower()

    # Single feedback AI summarization persisted to feedbacks.ai_summary
    first_unassigned_id = unassigned_before[0]["id"]
    sum_resp = api_client.post(
        f"/api/feedbacks/{first_unassigned_id}/summarize/",
        {"use_llm": False},
        format="json",
    )
    assert sum_resp.status_code == 200
    assert sum_resp.json()["ai_summary"]
    assert sum_resp.json()["feedback"]["ai_summary"] == sum_resp.json()["ai_summary"]

    # Similarity search on a feedback item
    sim_resp = api_client.get(f"/api/feedbacks/{first_unassigned_id}/similar/?min_similarity=0.1")
    assert sim_resp.status_code == 200
    assert len(sim_resp.json()["matches"]) >= 1
