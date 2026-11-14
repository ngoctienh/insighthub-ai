import os
import pytest
from django.test import override_settings


DEMO_PASS = os.getenv("DEMO_USER_PASSWORD", "InsightDemo!2026")


@pytest.mark.django_db
def test_register_forces_customer_role_and_login_flow(api_client):
    reg_resp = api_client.post(
        "/api/auth/register/",
        {
            "username": "new_cust",
            "email": "new_cust@example.com",
            "full_name": "Khách Hàng Mới",
            "password": "StrongPassword!2026",
            "role_code": "ADMIN",  # Must be ignored by server
        },
        format="json",
    )
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert data["user"]["role_code"] == "CUSTOMER"
    assert "access" in data and "refresh" in data

    # Login via email
    login_resp = api_client.post(
        "/api/auth/login/",
        {"identifier": "new_cust@example.com", "password": "StrongPassword!2026"},
        format="json",
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()

    # Profile update
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    me_patch = api_client.patch("/api/auth/me/", {"full_name": "Nguyễn Khách Hàng"}, format="json")
    assert me_patch.status_code == 200
    assert me_patch.json()["full_name"] == "Nguyễn Khách Hàng"

    # Logout blacklists refresh token
    logout_resp = api_client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
    assert logout_resp.status_code == 200
    refresh_after = api_client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert refresh_after.status_code == 401


@pytest.mark.django_db
def test_forgot_and_reset_password(api_client, seeded_db):
    # Production (DEBUG=False) must NOT leak reset token in HTTP body
    with override_settings(DEBUG=False):
        prod_resp = api_client.post(
            "/api/auth/forgot-password/",
            {"email": "an.nguyen@gmail.com"},
            format="json",
        )
        assert prod_resp.status_code == 200
        assert "dev_reset_token" not in prod_resp.json()

    # Local dev (DEBUG=True) exposes dev_reset_token for testing without SMTP
    with override_settings(DEBUG=True):
        forgot_resp = api_client.post(
            "/api/auth/forgot-password/",
            {"email": "an.nguyen@gmail.com"},
            format="json",
        )
        assert forgot_resp.status_code == 200
        reset_token = forgot_resp.json().get("dev_reset_token")
        assert reset_token

    reset_resp = api_client.post(
        "/api/auth/reset-password/",
        {"token": reset_token, "new_password": "ResetPass!2026New"},
        format="json",
    )
    assert reset_resp.status_code == 200

    login_resp = api_client.post(
        "/api/auth/login/",
        {"identifier": "customer_an", "password": "ResetPass!2026New"},
        format="json",
    )
    assert login_resp.status_code == 200


@pytest.mark.django_db
def test_rbac_enforced_at_api_level(api_client, seeded_db):
    # 1. Customer cannot access user management, insights, private roadmap, or AI trigger
    cust_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "customer_an", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {cust_login['access']}")

    assert api_client.get("/api/users/").status_code == 403
    assert api_client.get("/api/insights/").status_code == 403
    assert api_client.get("/api/roadmap/").status_code == 403
    assert api_client.post("/api/ai/analyze/", {}, format="json").status_code == 403

    # Customer only sees their own feedbacks in /api/feedbacks/
    fb_list = api_client.get("/api/feedbacks/?page_size=100").json()["results"]
    assert len(fb_list) > 0
    assert all(item["sender_email"] == "an.nguyen@gmail.com" for item in fb_list)

    # Customer cannot see internal comments
    first_fb_id = fb_list[0]["id"]
    comments = api_client.get(f"/api/feedbacks/{first_fb_id}/comments/").json()
    assert all(not c["is_internal"] for c in comments)

    # 2. Developer cannot run AI pipeline, create roadmap, or manage users
    dev_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "dev_tuan", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {dev_login['access']}")

    assert api_client.post("/api/ai/analyze/", {}, format="json").status_code == 403
    assert api_client.post("/api/users/", {"username": "x"}, format="json").status_code == 403
    assert api_client.post(
        "/api/roadmap/",
        {"product": 1, "title": "Unauthorized", "description": "test"},
        format="json",
    ).status_code == 403

    # 3. Admin can create new user with role
    admin_login = api_client.post(
        "/api/auth/login/",
        {"identifier": "admin", "password": DEMO_PASS},
        format="json",
    ).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_login['access']}")

    create_user_resp = api_client.post(
        "/api/users/",
        {
            "username": "pm_lan",
            "email": "lan.pm@insighthub.vn",
            "full_name": "Vũ Ngọc Lan",
            "role_code": "PRODUCT_MANAGER",
            "password": "StrongUser!2026",
        },
        format="json",
    )
    assert create_user_resp.status_code == 201
    assert create_user_resp.json()["role_code"] == "PRODUCT_MANAGER"
