import json
import os
import pytest

from apps.accounts.models import Role
from apps.feedbacks.models import Feedback, FeedbackReply, Product, Tag
from apps.insights.models import InsightGroup
from apps.notifications.models import Notification
from apps.roadmap.models import RoadmapItem

DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_web_public_pages_and_auth_flow(client, seeded_db):
    # Public landing & public roadmap work anonymously and never leak private items
    assert client.get("/").status_code == 200
    pub_resp = client.get("/public-roadmap/")
    assert pub_resp.status_code == 200
    assert "Tái cấu trúc Search Index" not in pub_resp.content.decode("utf-8")

    # Protected page redirects to /login/
    dash_unauth = client.get("/dashboard/")
    assert dash_unauth.status_code == 302
    assert "/login/" in dash_unauth["Location"]

    # Register forces CUSTOMER role & redirects to /portal/
    reg_resp = client.post(
        "/register/",
        {
            "full_name": "Khách Web Mới",
            "username": "web_cust_1",
            "email": "web_cust_1@example.com",
            "password": "StrongPassword!2026",
        },
    )
    assert reg_resp.status_code == 302
    assert reg_resp["Location"] == "/portal/"

    # Customer can access /portal/, /inbox/, /notifications/, /settings/, but gets 403 on internal pages
    assert client.get("/portal/").status_code == 200
    assert client.get("/inbox/").status_code == 200
    assert client.get("/notifications/").status_code == 200
    assert client.get("/settings/").status_code == 200
    assert client.get("/dashboard/").status_code == 403
    assert client.get("/insights/").status_code == 403
    assert client.get("/kanban/").status_code == 403
    assert client.get("/roadmap/").status_code == 403
    assert client.get("/users/").status_code == 403

    # Logout & login via email as PM
    client.post("/logout/")
    login_resp = client.post(
        "/login/",
        {"identifier": "pm@insighthub.vn", "password": DEMO_PASS},
    )
    assert login_resp.status_code == 302
    assert login_resp["Location"] == "/dashboard/"


@pytest.mark.django_db
def test_web_pm_workflow_ai_kanban_roadmap(client, seeded_db, bridge_real_ai_service):
    client.post("/login/", {"identifier": "pm_minh", "password": DEMO_PASS})

    # Render all internal screens cleanly
    for route in ("/dashboard/", "/inbox/", "/sources/", "/insights/", "/kanban/", "/roadmap/", "/users/", "/settings/"):
        resp = client.get(route)
        assert resp.status_code == 200, f"Failed rendering {route}"

    # Multi-source ingest through Django web view
    product = Product.objects.first()
    ingest_resp = client.post(
        "/sources/",
        {
            "source_code": "EMAIL",
            "product_id": product.id,
            "sender_name": "Web Email Tester",
            "sender_email": "tester@example.com",
            "title": "Lỗi xác nhận thanh toán MoMo từ Web UI",
            "content": "Thanh toán ví MoMo bị timeout không lên đơn hàng.",
            "impact_level": "HIGH",
        },
    )
    assert ingest_resp.status_code == 302
    new_fb = Feedback.objects.order_by("-id").first()
    assert new_fb.title == "Lỗi xác nhận thanh toán MoMo từ Web UI"

    # Feedback detail AI summarize & similarity search
    fb_detail_url = f"/inbox/{new_fb.id}/"
    assert client.get(fb_detail_url).status_code == 200
    assert client.post(fb_detail_url, {"action": "summarize"}).status_code == 302
    new_fb.refresh_from_db()
    assert new_fb.ai_summary
    sim_resp = client.post(fb_detail_url, {"action": "find_similar"})
    assert sim_resp.status_code == 200

    # Run AI clustering via web view
    before_insights = InsightGroup.objects.count()
    ai_resp = client.post(
        "/insights/",
        {
            "action": "run_ai",
            "similarity_threshold": "0.65",
            "eps": "0.62",
            "min_samples": "2",
        },
    )
    assert ai_resp.status_code == 302
    assert InsightGroup.objects.count() > before_insights

    # Edit Insight & manual priority override + vote + regenerate reply
    insight = InsightGroup.objects.order_by("-id").first()
    ins_url = f"/insights/{insight.id}/"
    assert client.get(ins_url).status_code == 200
    client.post(
        ins_url,
        {
            "action": "edit_insight",
            "title": "Nhóm lỗi thanh toán ưu tiên khẩn",
            "description": "Mô tả đã được PM chỉnh sửa.",
            "priority_score": "88.5",
        },
    )
    insight.refresh_from_db()
    assert insight.priority_level == "CRITICAL"
    assert insight.title == "Nhóm lỗi thanh toán ưu tiên khẩn"

    client.post(ins_url, {"action": "vote"})
    assert insight.votes.count() == 1

    client.post(ins_url, {"action": "regenerate_reply", "tone": "update"})
    insight.refresh_from_db()
    assert "roadmap" in insight.draft_customer_reply.lower()

    # Kanban JSON drag-and-drop move
    kanban_resp = client.post(
        "/kanban/?mode=insights",
        data=json.dumps({"action": "move_insight", "item_id": insight.id, "status": "PLANNED"}),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )
    assert kanban_resp.status_code == 200
    insight.refresh_from_db()
    assert insight.status == "PLANNED"

    # Promote to roadmap from Insight detail
    before_rm = RoadmapItem.objects.count()
    client.post(
        ins_url,
        {
            "action": "promote_roadmap",
            "title": "Nâng cấp cổng MoMo",
            "description": "Chi tiết kỹ thuật nội bộ",
            "public_description": "Cải thiện ổn định thanh toán ví điện tử",
            "status": "PLANNED",
            "visibility": "PUBLIC",
            "quarter": "Q1 2027",
        },
    )
    assert RoadmapItem.objects.count() == before_rm + 1


@pytest.mark.django_db
def test_web_admin_user_and_dynamic_role_permissions(client, seeded_db):
    client.post("/login/", {"identifier": "admin", "password": DEMO_PASS})

    # Admin creates a new user
    create_resp = client.post(
        "/users/",
        {
            "action": "create_user",
            "username": "dev_nam",
            "email": "nam.dev@insighthub.vn",
            "full_name": "Nguyễn Hải Nam",
            "role_code": "DEVELOPER",
            "job_title": "Backend Engineer",
            "password": "StrongUser!2026",
        },
    )
    assert create_resp.status_code == 302

    # Admin toggles `ai_run` permission for DEVELOPER via AJAX JSON
    dev_role = Role.objects.get(code=Role.DEVELOPER)
    assert "ai_run" not in dev_role.effective_permissions()
    toggle_resp = client.post(
        "/users/",
        data=json.dumps(
            {
                "action": "toggle_permission",
                "role_id": dev_role.id,
                "feature_key": "ai_run",
                "enabled": True,
            }
        ),
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )
    assert toggle_resp.status_code == 200
    dev_role.refresh_from_db()
    assert "ai_run" in dev_role.effective_permissions()

    # Reset defaults restores DEVELOPER permissions
    client.post("/users/", {"action": "reset_defaults"})
    dev_role.refresh_from_db()
    assert "ai_run" not in dev_role.effective_permissions()


@pytest.mark.django_db
def test_api_celery_task_status_and_customer_patch_validation(api_client, seeded_db, monkeypatch):
    # Customer PATCH with forbidden-only fields returns 403 (not silent 200)
    cust_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "customer_an", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {cust_login['access']}")
    new_fb = Feedback.objects.filter(author__username="customer_an", status="NEW").first()
    if not new_fb:
        prod = Product.objects.first()
        from apps.feedbacks.models import FeedbackSource
        src = FeedbackSource.objects.first()
        new_fb = Feedback.objects.create(
            title="Customer own new",
            content="Content",
            author_id=cust_login["user"]["id"],
            sender_name="An",
            sender_email="an.nguyen@gmail.com",
            product=prod,
            source=src,
            status="NEW",
        )
    bad_patch = api_client.patch(f"/api/feedbacks/{new_fb.id}/", {"status": "DONE"}, format="json")
    assert bad_patch.status_code == 403

    # Celery task status endpoint returns normalized JSON
    pm_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "pm_minh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {pm_login['access']}")

    class _FakeAsyncResult:
        def __init__(self, task_id, app=None):
            self.state = "SUCCESS"
            self.result = {"status": "COMPLETED", "metrics": {"processed_count": 4}}

    monkeypatch.setattr("apps.insights.services.AsyncResult", _FakeAsyncResult)
    task_resp = api_client.get("/api/ai/tasks/fake-task-123/")
    assert task_resp.status_code == 200
    assert task_resp.json()["ready"] is True
    assert task_resp.json()["state"] == "SUCCESS"


@pytest.mark.django_db
def test_manual_customer_reply_on_feedback_and_insight(client, api_client, seeded_db):
    # PM posts a manual reply directly to customer_an's feedback via web view
    cust_fb = Feedback.objects.filter(author__username="customer_an").first()
    assert cust_fb is not None

    client.post("/login/", {"identifier": "pm_minh", "password": DEMO_PASS})
    reply_resp = client.post(
        f"/inbox/{cust_fb.id}/",
        {"action": "send_reply", "message": "Đội sản phẩm đã tiếp nhận và đang kiểm tra lỗi này."},
    )
    assert reply_resp.status_code == 302
    assert FeedbackReply.objects.filter(feedback=cust_fb, is_staff_reply=True).count() == 1
    assert Notification.objects.filter(
        recipient=cust_fb.author,
        feedback=cust_fb,
        event_type=Notification.EVENT_FEEDBACK_REPLIED,
    ).exists()

    # PM saves & broadcasts manual reply from Insight detail to member feedbacks
    insight = InsightGroup.objects.first()
    assert insight is not None
    save_resp = client.post(
        f"/insights/{insight.id}/",
        {"action": "save_draft_reply", "message": "Cảm ơn bạn, bản vá sẽ phát hành tuần này."},
    )
    assert save_resp.status_code == 302
    insight.refresh_from_db()
    assert insight.draft_customer_reply == "Cảm ơn bạn, bản vá sẽ phát hành tuần này."

    group_resp = client.post(
        f"/insights/{insight.id}/",
        {"action": "send_group_reply", "message": "Phản hồi chung từ nhóm Insight."},
    )
    assert group_resp.status_code == 302
    member_fb_ids = list(insight.insight_feedback_links.values_list("feedback_id", flat=True))
    assert FeedbackReply.objects.filter(feedback_id__in=member_fb_ids, message="Phản hồi chung từ nhóm Insight.").count() == len(set(member_fb_ids))

    # Customer logs in, sees staff reply on /inbox/<id>/ and /portal/, and posts a follow-up reply
    client.post("/logout/")
    client.post("/login/", {"identifier": "customer_an", "password": DEMO_PASS})
    fb_page = client.get(f"/inbox/{cust_fb.id}/").content.decode("utf-8")
    assert "Đội sản phẩm đã tiếp nhận và đang kiểm tra lỗi này." in fb_page

    cust_follow = client.post(
        f"/inbox/{cust_fb.id}/",
        {"action": "send_reply", "message": "Cảm ơn đội ngũ, mình bị lỗi trên iOS 18."},
    )
    assert cust_follow.status_code == 302
    assert FeedbackReply.objects.filter(feedback=cust_fb, is_staff_reply=False).count() == 1

    # API reply endpoint works for authenticated CS user
    cs_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "cs_linh", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {cs_login['access']}")
    api_reply = api_client.post(
        f"/api/feedbacks/{cust_fb.id}/reply/",
        {"message": "CSKH đã ghi nhận thông tin iOS 18 của bạn."},
        format="json",
    )
    assert api_reply.status_code == 201
    assert api_reply.json()["is_staff_reply"] is True
