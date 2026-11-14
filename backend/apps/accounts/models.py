from django.db import models
from django.contrib.auth.models import AbstractUser


class Role(models.Model):
    ADMIN = "ADMIN"
    PRODUCT_MANAGER = "PRODUCT_MANAGER"
    DEVELOPER = "DEVELOPER"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    CUSTOMER = "CUSTOMER"

    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (PRODUCT_MANAGER, "Product Manager"),
        (DEVELOPER, "Developer"),
        (CUSTOMER_SUPPORT, "Customer Support"),
        (CUSTOMER, "Customer"),
    ]

    code = models.CharField(max_length=32, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    permissions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "roles"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class User(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150, blank=True, default="")
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    job_title = models.CharField(max_length=120, blank=True, default="")
    department = models.CharField(max_length=120, blank=True, default="")
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    email_notifications_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
        ]

    @property
    def role_code(self) -> str:
        if self.role_id:
            return self.role.code
        return Role.ADMIN if self.is_superuser else Role.CUSTOMER

    def display_name(self) -> str:
        return self.full_name.strip() or self.username

    def __str__(self) -> str:
        return f"{self.display_name()} ({self.role_code})"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_tokens"
        ordering = ["-created_at"]
