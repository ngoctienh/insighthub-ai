from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "insighthub-ai-service"


def test_full_analyze_pipeline_vietnamese_food_delivery():
    payload = {
        "similarity_threshold": 0.65,
        "eps": 0.62,
        "min_samples": 2,
        "use_llm": False,
        "feedbacks": [
            {
                "id": 1,
                "code": "FB-0001",
                "title": "Không thể thanh toán đơn hàng",
                "content": "Mình bấm thanh toán đơn hàng bằng thẻ nhưng hệ thống báo lỗi không xử lý được.",
                "impact_level": "CRITICAL",
                "votes_count": 12,
                "sender_email": "a@example.com",
                "source_code": "WEB_FORM",
            },
            {
                "id": 2,
                "code": "FB-0002",
                "title": "Thanh toán bị lỗi khi dùng thẻ",
                "content": "Không thể thanh toán đơn hàng, ứng dụng không xử lý giao dịch thẻ tín dụng.",
                "impact_level": "CRITICAL",
                "votes_count": 9,
                "sender_email": "b@example.com",
                "source_code": "EMAIL",
            },
            {
                "id": 3,
                "code": "FB-0003",
                "title": "Ứng dụng không xử lý giao dịch ví MoMo",
                "content": "Thanh toán bằng ví bị treo ở màn hình xác nhận giao dịch.",
                "impact_level": "HIGH",
                "votes_count": 7,
                "sender_email": "c@example.com",
                "source_code": "LIVE_CHAT",
            },
            {
                "id": 4,
                "code": "FB-0004",
                "title": "Tài xế giao hàng quá muộn",
                "content": "Đơn hàng giao quá lâu, tài xế đến muộn hơn 40 phút so với dự kiến.",
                "impact_level": "HIGH",
                "votes_count": 8,
                "sender_email": "d@example.com",
                "source_code": "COMMUNITY",
            },
            {
                "id": 5,
                "code": "FB-0005",
                "title": "Thời gian giao hàng không chính xác",
                "content": "App báo 20 phút nhưng shipper giao hàng chậm gần một tiếng đồng hồ.",
                "impact_level": "MEDIUM",
                "votes_count": 4,
                "sender_email": "e@example.com",
                "source_code": "WEB_FORM",
            },
            {
                "id": 6,
                "code": "FB-0006",
                "title": "Đề xuất thêm chế độ giao diện tối",
                "content": "Mong đội ngũ phát triển bổ sung dark mode cho mắt đỡ mỏi vào buổi tối.",
                "impact_level": "LOW",
                "votes_count": 1,
                "sender_email": "f@example.com",
                "source_code": "COMMUNITY",
            },
        ],
    }

    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["stats"]["processed_count"] == 6
    assert len(data["embeddings"]) == 6
    assert len(data["clusters"]) >= 2
    assert 6 in data["unassigned_feedback_ids"]

    top_cluster = data["clusters"][0]
    expected_priority = round(
        0.40 * top_cluster["volume_score"]
        + 0.35 * top_cluster["impact_score"]
        + 0.25 * top_cluster["severity_score"],
        1,
    )
    assert abs(top_cluster["priority_score"] - expected_priority) <= 0.2
    assert top_cluster["draft_customer_reply"]
    assert len(top_cluster["possible_causes"]) >= 1
    assert len(top_cluster["ai_recommendations"]) >= 1

    payment_cluster = next(
        (c for c in data["clusters"] if {m["feedback_id"] for m in c["members"]} & {1, 2}),
        None,
    )
    assert payment_cluster is not None
    payment_ids = {m["feedback_id"] for m in payment_cluster["members"]}
    assert {1, 2}.issubset(payment_ids)


def test_similarity_search_and_draft_reply():
    sim_resp = client.post(
        "/similarity/search",
        json={
            "target": {
                "id": 10,
                "code": "FB-0010",
                "title": "Không nhận được thông báo tài xế tới",
                "content": "Ứng dụng không gửi push notification khi tài xế đến nơi.",
            },
            "candidates": [
                {
                    "id": 11,
                    "code": "FB-0011",
                    "title": "App không báo khi shipper đến",
                    "content": "Không nhận được thông báo trạng thái đơn hàng.",
                },
                {
                    "id": 12,
                    "code": "FB-0012",
                    "title": "Màu chữ menu hơi nhỏ",
                    "content": "Nên tăng kích thước font chữ phần mô tả món ăn.",
                },
            ],
            "top_k": 2,
            "min_similarity": 0.1,
            "use_llm": False,
        },
    )
    assert sim_resp.status_code == 200
    matches = sim_resp.json()["matches"]
    assert len(matches) >= 1
    assert matches[0]["feedback_id"] == 11

    reply_resp = client.post(
        "/draft-reply",
        json={
            "insight_title": "Thiếu thông báo khi tài xế tới",
            "insight_summary": "Nhiều người dùng không nhận được push notification.",
            "sample_feedbacks": ["Không nhận được thông báo khi shipper tới"],
            "tone": "resolved",
            "use_llm": False,
        },
    )
    assert reply_resp.status_code == 200
    assert "cập nhật" in reply_resp.json()["draft_reply"].lower()
