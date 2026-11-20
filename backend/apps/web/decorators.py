from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.accounts.models import Role
from apps.accounts.permissions import has_feature


def get_user_home_url(user) -> str:
    if not user or not user.is_authenticated:
        return "/login/"
    if user.role_code == Role.CUSTOMER:
        return "/portal/"
    if has_feature(user, "dashboard"):
        return "/dashboard/"
    if has_feature(user, "inbox"):
        return "/inbox/"
    return "/settings/"


def is_json_request(request) -> bool:
    accept = request.headers.get("Accept", "")
    xrw = request.headers.get("X-Requested-With", "")
    ct = request.content_type or ""
    return "application/json" in accept or xrw == "XMLHttpRequest" or "application/json" in ct


def render_forbidden(request, message: str = "Bạn không có quyền truy cập chức năng này."):
    if is_json_request(request):
        return JsonResponse({"detail": message}, status=403)
    return render(
        request,
        "pages/403.html",
        {"error_message": message, "home_url": get_user_home_url(request.user)},
        status=403,
    )


def web_feature_required(*feature_keys: str):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if any(has_feature(request.user, key) for key in feature_keys):
                return view_func(request, *args, **kwargs)
            return render_forbidden(
                request,
                "Vai trò của bạn chưa được cấp quyền sử dụng chức năng này.",
            )

        return _wrapped

    return decorator


def web_internal_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.role_code in (
            Role.ADMIN,
            Role.PRODUCT_MANAGER,
            Role.DEVELOPER,
            Role.CUSTOMER_SUPPORT,
        ):
            return view_func(request, *args, **kwargs)
        return render_forbidden(
            request,
            "Tài khoản khách hàng không có quyền truy cập khu vực nội bộ này.",
        )

    return _wrapped


def web_pm_or_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.role_code in (Role.ADMIN, Role.PRODUCT_MANAGER):
            return view_func(request, *args, **kwargs)
        return render_forbidden(
            request,
            "Chỉ Product Manager hoặc Admin mới có quyền thực hiện thao tác này.",
        )

    return _wrapped


def web_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.role_code == Role.ADMIN:
            return view_func(request, *args, **kwargs)
        return render_forbidden(
            request,
            "Chỉ quản trị viên (ADMIN) mới có quyền thực hiện thao tác này.",
        )

    return _wrapped
