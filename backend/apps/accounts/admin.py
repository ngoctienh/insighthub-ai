from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import PasswordResetToken, Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "created_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "full_name", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("InsightHub Profile", {"fields": ("full_name", "role", "job_title", "department", "avatar_url", "email_notifications_enabled")}),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
