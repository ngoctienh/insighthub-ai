import os
import pytest


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

    # Profile update & change password
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    me_patch = api_client.patch("/api/auth/me/", {"full_name": "Nguyễn Khách Hàng"}, format="json")
    assert me_patch.status_code == 200
    assert me_patch.json()["full_name"] == "Nguyễn Khách Hàng"

    chg_resp = api_client.post(
        "/api/auth/change-password/",
        {"old_password": "StrongPassword!2026", "new_password": "NewStrongPass!2026"},
        format="json",
    )
    assert chg_resp.status_code == 200

    # Logout blacklists refresh token
    logout_resp = api_client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
    assert logout_resp.status_code == 200
    refresh_after = api_client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert refresh_after.status_code == 401


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

    # 4. Admin can toggle feature permissions on a role and enforce dynamically on API
    roles_list = api_client.get("/api/roles/").json()
    dev_role = next(r for r in roles_list if r["code"] == "DEVELOPER")
    assert "ai_run" not in dev_role["permissions"]

    patch_resp = api_client.patch(
        f"/api/roles/{dev_role['id']}/",
        {"permissions": dev_role["permissions"] + ["ai_run"]},
        format="json",
    )
    assert patch_resp.status_code == 200
    assert "ai_run" in patch_resp.json()["permissions"]

    # Developer's /auth/me/ now includes ai_run; restore defaults afterward
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {dev_login['access']}")
    me_dev = api_client.get("/api/auth/me/").json()
    assert "ai_run" in me_dev["permissions"]

    # Non-admin cannot modify roles or reset defaults
    assert api_client.post("/api/roles/reset_defaults/").status_code == 403

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_login['access']}")
    reset_resp = api_client.post("/api/roles/reset_defaults/")
    assert reset_resp.status_code == 200
    dev_reset = next(r for r in reset_resp.json() if r["code"] == "DEVELOPER")
    assert "ai_run" not in dev_reset["permissions"]
