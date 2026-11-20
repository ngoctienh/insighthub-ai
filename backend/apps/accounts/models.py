from django.contrib.auth.models import AbstractUser
from django.db import models


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

    FEATURE_MODULES = [
        ("dashboard", "Dashboard", "Xem thống kê KPI và biểu đồ"),
        ("inbox", "Feedback Inbox", "Xem danh sách và chi tiết phản hồi"),
        ("sources", "Multi-source Hub", "Tiếp nhận phản hồi đa nguồn"),
        ("insights", "AI Insights", "Xem nhóm vấn đề & gợi ý trùng lặp"),
        ("ai_run", "Chạy AI Engine", "Kích hoạt AI phân tích & gom nhóm"),
        ("kanban", "Kanban Board", "Xem và chuyển trạng thái Kanban"),
        ("roadmap", "Product Roadmap", "Xem lộ trình sản phẩm nội bộ"),
        ("users", "Người dùng", "Truy cập trang danh sách & phân quyền"),
    ]
    ALL_FEATURE_KEYS = [item[0] for item in FEATURE_MODULES]

    DEFAULT_PERMISSIONS = {
        ADMIN: list(ALL_FEATURE_KEYS),
        PRODUCT_MANAGER: list(ALL_FEATURE_KEYS),
        DEVELOPER: ["dashboard", "inbox", "sources", "insights", "kanban", "roadmap", "users"],
        CUSTOMER_SUPPORT: ["dashboard", "inbox", "sources", "insights", "kanban", "roadmap", "users"],
        CUSTOMER: ["inbox"],
    }

    code = models.CharField(max_length=32, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    permissions = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "roles"
        ordering = ["id"]

    def effective_permissions(self) -> list[str]:
        if self.code == self.ADMIN:
            return list(self.ALL_FEATURE_KEYS)
        if isinstance(self.permissions, list):
            return [k for k in self.permissions if k in self.ALL_FEATURE_KEYS]
        return list(self.DEFAULT_PERMISSIONS.get(self.code, []))

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class User(AbstractUser):
    first_name = None
    last_name = None

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

    def get_feature_permissions(self) -> list[str]:
        if self.role_code == Role.ADMIN:
            return list(Role.ALL_FEATURE_KEYS)
        if self.role_id:
            return self.role.effective_permissions()
        return list(Role.DEFAULT_PERMISSIONS.get(self.role_code, []))

    def has_feature_permission(self, feature_key: str) -> bool:
        return feature_key in self.get_feature_permissions()

    def display_name(self) -> str:
        return self.full_name.strip() or self.username

    def __str__(self) -> str:
        return f"{self.display_name()} ({self.role_code})"
