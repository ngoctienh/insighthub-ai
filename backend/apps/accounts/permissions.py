from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


def get_role_code(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    return user.role_code


def has_feature(user, feature_key: str) -> bool:
    return bool(user and user.is_authenticated and user.has_feature_permission(feature_key))


def require_feature(*feature_keys: str):
    """Build a DRF permission class allowing access if the user's role enables any listed feature."""

    class FeaturePermission(BasePermission):
        message = "Vai trò của bạn chưa được cấp quyền sử dụng chức năng này."

        def has_permission(self, request, view):
            return any(has_feature(request.user, key) for key in feature_keys)

    return FeaturePermission


class IsAdmin(BasePermission):
    message = "Chỉ quản trị viên (ADMIN) mới có quyền thực hiện thao tác này."

    def has_permission(self, request, view):
        return get_role_code(request.user) == Role.ADMIN


class IsPMOrAdmin(BasePermission):
    message = "Chỉ Product Manager hoặc Admin mới có quyền thực hiện thao tác này."

    def has_permission(self, request, view):
        return get_role_code(request.user) in (Role.ADMIN, Role.PRODUCT_MANAGER)


class IsInternalTeam(BasePermission):
    message = "Tài khoản khách hàng không có quyền truy cập khu vực nội bộ này."

    def has_permission(self, request, view):
        return get_role_code(request.user) in (
            Role.ADMIN,
            Role.PRODUCT_MANAGER,
            Role.DEVELOPER,
            Role.CUSTOMER_SUPPORT,
        )


class UserManagementPermission(BasePermission):
    """
    ADMIN: full user CRUD & role management.
    Users with `users` permission (or internal team querying ?internal_only=true for assignment): read-only.
    Others: denied (403).
    """

    def has_permission(self, request, view):
        role = get_role_code(request.user)
        if not role:
            return False
        if role == Role.ADMIN:
            return True
        if request.method not in SAFE_METHODS:
            return False
        if has_feature(request.user, "users"):
            return True
        internal_only = request.query_params.get("internal_only") in ("1", "true", "True")
        return internal_only and role in (
            Role.PRODUCT_MANAGER,
            Role.DEVELOPER,
            Role.CUSTOMER_SUPPORT,
        )
