import json

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.accounts.serializers import (
    AdminUserWriteSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    RoleSerializer,
    ensure_default_roles,
)
from apps.feedbacks.models import Product, Tag
from apps.feedbacks.serializers import ProductSerializer, TagSerializer
from apps.web.decorators import (
    get_user_home_url,
    is_json_request,
    render_forbidden,
    web_feature_required,
)
from .helpers import format_serializer_error

DEMO_ACCOUNTS = [
    {"label": "Admin", "identifier": "admin", "role": "ADMIN"},
    {"label": "Product Manager", "identifier": "pm_minh", "role": "PRODUCT_MANAGER"},
    {"label": "Developer", "identifier": "dev_tuan", "role": "DEVELOPER"},
    {"label": "Customer Support", "identifier": "cs_linh", "role": "CUSTOMER_SUPPORT"},
    {"label": "Customer", "identifier": "customer_an", "role": "CUSTOMER"},
]


def landing_view(request):
    return render(request, "pages/landing.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_user_home_url(request.user))

    error = ""
    identifier = request.POST.get("identifier", "").strip() if request.method == "POST" else ""
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        password = request.POST.get("password", "")
        serializer = LoginSerializer(data={"identifier": identifier, "password": password})
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data["user"]
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
            auth_login(request, user)
            messages.success(request, f"Chào mừng {user.display_name()}!")
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect(get_user_home_url(user))
        except ValidationError as exc:
            error = format_serializer_error(exc, "Đăng nhập thất bại.")

    return render(
        request,
        "pages/login.html",
        {
            "error": error,
            "identifier": identifier,
            "next": next_url,
            "demo_accounts": DEMO_ACCOUNTS,
        },
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect(get_user_home_url(request.user))

    error = ""
    form_data = {
        "full_name": "",
        "username": "",
        "email": "",
    }
    if request.method == "POST":
        form_data = {
            "full_name": request.POST.get("full_name", "").strip(),
            "username": request.POST.get("username", "").strip(),
            "email": request.POST.get("email", "").strip(),
        }
        serializer = RegisterSerializer(
            data={**form_data, "password": request.POST.get("password", "")}
        )
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            auth_login(request, user)
            messages.success(request, "Đăng ký tài khoản thành công!")
            return redirect("/portal/")
        except ValidationError as exc:
            error = format_serializer_error(exc, "Đăng ký thất bại.")

    return render(request, "pages/register.html", {"error": error, "form": form_data})


def logout_view(request):
    if request.method == "POST":
        auth_logout(request)
        messages.info(request, "Bạn đã đăng xuất khỏi hệ thống.")
    return redirect("web-login")


@login_required
def settings_view(request):
    can_manage_catalog = request.user.role_code in (Role.ADMIN, Role.PRODUCT_MANAGER)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "update_profile":
            serializer = ProfileUpdateSerializer(
                request.user,
                data={
                    "full_name": request.POST.get("full_name", ""),
                    "job_title": request.POST.get("job_title", ""),
                },
                partial=True,
            )
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save()
                messages.success(request, "Đã cập nhật hồ sơ cá nhân.")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
        elif action == "change_password":
            old_password = request.POST.get("old_password", "")
            new_password = request.POST.get("new_password", "")
            serializer = ChangePasswordSerializer(
                data={"old_password": old_password, "new_password": new_password},
                context={"user": request.user},
            )
            try:
                serializer.is_valid(raise_exception=True)
                if not request.user.check_password(old_password):
                    messages.error(request, "Mật khẩu hiện tại không đúng.")
                else:
                    request.user.set_password(new_password)
                    request.user.save(update_fields=["password"])
                    update_session_auth_hash(request, request.user)
                    messages.success(request, "Đổi mật khẩu thành công.")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
        elif action == "create_product":
            if not can_manage_catalog:
                return render_forbidden(request)
            serializer = ProductSerializer(
                data={
                    "name": request.POST.get("name", "").strip(),
                    "slug": request.POST.get("slug", "").strip(),
                    "description": request.POST.get("description", "").strip(),
                }
            )
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save()
                messages.success(request, "Đã thêm sản phẩm mới!")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
        elif action == "create_tag":
            if not can_manage_catalog:
                return render_forbidden(request)
            serializer = TagSerializer(
                data={
                    "name": request.POST.get("name", "").strip(),
                    "slug": request.POST.get("slug", "").strip(),
                    "color": request.POST.get("color", "#4f46e5").strip(),
                }
            )
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save()
                messages.success(request, "Đã thêm nhãn phân loại mới!")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))

        return redirect("web-settings")

    products = (
        Product.objects.annotate(feedback_count=Count("feedbacks", distinct=True))
        if can_manage_catalog
        else []
    )
    tags = Tag.objects.all() if can_manage_catalog else []

    return render(
        request,
        "pages/settings.html",
        {
            "active_nav": "settings",
            "can_manage_catalog": can_manage_catalog,
            "products": products,
            "tags": tags,
        },
    )


@web_feature_required("users")
def users_view(request):
    ensure_default_roles()
    is_admin = request.user.role_code == Role.ADMIN

    if request.method == "POST":
        if not is_admin:
            return render_forbidden(request, "Chỉ quản trị viên (ADMIN) mới có quyền chỉnh sửa người dùng & vai trò.")

        if is_json_request(request):
            try:
                body = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return JsonResponse({"detail": "Payload JSON không hợp lệ."}, status=400)

            if body.get("action") == "toggle_permission":
                role = get_object_or_404(Role, pk=body.get("role_id"))
                if role.code == Role.ADMIN:
                    return JsonResponse({"detail": "Admin luôn giữ toàn quyền hệ thống."}, status=400)
                feature_key = body.get("feature_key")
                enabled = bool(body.get("enabled"))
                current = set(role.effective_permissions())
                if enabled:
                    current.add(feature_key)
                else:
                    current.discard(feature_key)
                serializer = RoleSerializer(role, data={"permissions": list(current)}, partial=True)
                try:
                    serializer.is_valid(raise_exception=True)
                    updated = serializer.save()
                    return JsonResponse(
                        {
                            "id": updated.id,
                            "code": updated.code,
                            "permissions": updated.effective_permissions(),
                        }
                    )
                except ValidationError as exc:
                    return JsonResponse({"detail": format_serializer_error(exc)}, status=400)

        action = request.POST.get("action", "")
        if action == "create_user":
            serializer = AdminUserWriteSerializer(
                data={
                    "username": request.POST.get("username", "").strip(),
                    "email": request.POST.get("email", "").strip(),
                    "full_name": request.POST.get("full_name", "").strip(),
                    "role_code": request.POST.get("role_code", Role.DEVELOPER),
                    "job_title": request.POST.get("job_title", "").strip(),
                    "password": request.POST.get("password", ""),
                }
            )
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save()
                messages.success(request, "Đã tạo tài khoản thành công.")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
        elif action == "edit_user":
            target = get_object_or_404(User, pk=request.POST.get("user_id"))
            payload = {
                "email": request.POST.get("email", "").strip(),
                "full_name": request.POST.get("full_name", "").strip(),
                "role_code": request.POST.get("role_code", target.role_code),
                "job_title": request.POST.get("job_title", "").strip(),
            }
            pwd = request.POST.get("password", "")
            if pwd:
                payload["password"] = pwd
            serializer = AdminUserWriteSerializer(target, data=payload, partial=True)
            try:
                serializer.is_valid(raise_exception=True)
                serializer.save()
                messages.success(request, "Đã cập nhật người dùng & phân quyền.")
            except ValidationError as exc:
                messages.error(request, format_serializer_error(exc))
        elif action == "toggle_active":
            target = get_object_or_404(User, pk=request.POST.get("user_id"))
            if target.id == request.user.id:
                messages.error(request, "Không thể tự vô hiệu hóa chính tài khoản đang đăng nhập.")
            else:
                target.is_active = not target.is_active
                target.save(update_fields=["is_active"])
                state_txt = "kích hoạt" if target.is_active else "vô hiệu hóa"
                messages.info(request, f"Đã {state_txt} tài khoản @{target.username}.")
        elif action == "reset_defaults":
            for role in Role.objects.all():
                role.permissions = list(Role.DEFAULT_PERMISSIONS.get(role.code, []))
                role.save(update_fields=["permissions"])
            messages.info(request, "Đã khôi phục quyền mặc định cho 5 vai trò.")

        return redirect("web-users")

    users = User.objects.select_related("role").order_by("id")
    roles = list(Role.objects.annotate(user_count=Count("users")).order_by("id"))
    role_rows = [
        {
            "role": r,
            "permissions": r.effective_permissions(),
        }
        for r in roles
    ]
    features = [
        {"key": k, "label": lbl, "description": desc}
        for k, lbl, desc in Role.FEATURE_MODULES
    ]

    return render(
        request,
        "pages/users.html",
        {
            "active_nav": "users",
            "users_list": users,
            "role_rows": role_rows,
            "features": features,
            "role_choices": Role.ROLE_CHOICES,
        },
    )
