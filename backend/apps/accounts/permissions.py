from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


def get_role_code(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    return user.role_code


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
    Internal team (PM/DEV/CS): read-only team directory for assignment.
    CUSTOMER: denied (403).
    """

    def has_permission(self, request, view):
        role = get_role_code(request.user)
        if not role or role == Role.CUSTOMER:
            return False
        if role == Role.ADMIN:
            return True
        return request.method in SAFE_METHODS
