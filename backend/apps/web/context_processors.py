from apps.accounts.models import Role
from apps.notifications.models import Notification
from .decorators import get_user_home_url


def web_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "is_internal": False,
            "is_pm_or_admin": False,
            "is_admin": False,
            "user_permissions": [],
            "unread_notifications_count": 0,
            "home_url": "/login/",
        }

    role_code = user.role_code
    is_internal = role_code in (
        Role.ADMIN,
        Role.PRODUCT_MANAGER,
        Role.DEVELOPER,
        Role.CUSTOMER_SUPPORT,
    )
    return {
        "is_internal": is_internal,
        "is_pm_or_admin": role_code in (Role.ADMIN, Role.PRODUCT_MANAGER),
        "is_admin": role_code == Role.ADMIN,
        "user_permissions": user.get_feature_permissions(),
        "unread_notifications_count": Notification.objects.filter(
            recipient=user, is_read=False
        ).count(),
        "home_url": get_user_home_url(user),
    }
