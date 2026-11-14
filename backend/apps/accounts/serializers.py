from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Role, User


DEFAULT_ROLE_DEFINITIONS = {
    Role.ADMIN: ("Admin", "Quản trị toàn bộ hệ thống, phân quyền và cấu hình.", ["*"]),
    Role.PRODUCT_MANAGER: (
        "Product Manager",
        "Quản lý feedback, chạy AI Engine, quản lý insight, Kanban và roadmap.",
        ["feedback:*", "insight:*", "kanban:*", "roadmap:*", "ai:run"],
    ),
    Role.DEVELOPER: (
        "Developer",
        "Xem và xử lý feedback/insight được phân công, cập nhật trạng thái và comment nội bộ.",
        ["feedback:assigned", "insight:view", "kanban:update_assigned", "comment:internal"],
    ),
    Role.CUSTOMER_SUPPORT: (
        "Customer Support",
        "Tiếp nhận phản hồi đa nguồn, phân loại, comment nội bộ và phản hồi khách hàng.",
        ["feedback:view_all", "feedback:triage", "insight:view", "comment:internal"],
    ),
    Role.CUSTOMER: (
        "Customer",
        "Gửi phản hồi, theo dõi trạng thái xử lý, nhận thông báo và xem Public Roadmap.",
        ["feedback:create", "feedback:own", "roadmap:public", "notification:own"],
    ),
}


def ensure_default_roles() -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for code, (name, desc, perms) in DEFAULT_ROLE_DEFINITIONS.items():
        role, _ = Role.objects.get_or_create(
            code=code,
            defaults={"name": name, "description": desc, "permissions": perms},
        )
        roles[code] = role
    return roles


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "permissions"]


class UserMinimalSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(read_only=True)
    role_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "display_name",
            "role_code",
            "role_name",
            "job_title",
            "department",
            "avatar_url",
            "is_active",
        ]

    def get_role_name(self, obj: User) -> str:
        return obj.role.name if obj.role_id else obj.role_code

    def get_display_name(self, obj: User) -> str:
        return obj.display_name()


class UserDetailSerializer(UserMinimalSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserMinimalSerializer.Meta):
        fields = UserMinimalSerializer.Meta.fields + [
            "permissions",
            "email_notifications_enabled",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def get_permissions(self, obj: User) -> list:
        if obj.role_id:
            return obj.role.permissions or []
        return ["*"] if obj.is_superuser else []


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value: str) -> str:
        val = value.strip()
        if User.objects.filter(username__iexact=val).exists():
            raise serializers.ValidationError("Tên đăng nhập đã tồn tại.")
        return val

    def validate_email(self, value: str) -> str:
        val = value.strip().lower()
        if User.objects.filter(email__iexact=val).exists():
            raise serializers.ValidationError("Email đã được sử dụng.")
        return val

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data):
        roles = ensure_default_roles()
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            full_name=validated_data["full_name"].strip(),
            password=validated_data["password"],
            role=roles[Role.CUSTOMER],
            job_title="Khách hàng",
            department="External",
        )
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Email hoặc username")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password", "")

        user = None
        if "@" in identifier:
            candidate = User.objects.filter(email__iexact=identifier).first()
            if candidate:
                user = authenticate(username=candidate.username, password=password)
        else:
            user = authenticate(username=identifier, password=password)

        if not user:
            raise serializers.ValidationError("Email/tên đăng nhập hoặc mật khẩu không chính xác.")
        if not user.is_active:
            raise serializers.ValidationError("Tài khoản này đã bị vô hiệu hóa.")
        attrs["user"] = user
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "full_name",
            "job_title",
            "department",
            "avatar_url",
            "email_notifications_enabled",
        ]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context.get("user"))
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value


class AdminUserWriteSerializer(serializers.ModelSerializer):
    role_code = serializers.ChoiceField(choices=Role.ROLE_CHOICES, write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "role_code",
            "job_title",
            "department",
            "avatar_url",
            "is_active",
            "email_notifications_enabled",
            "password",
        ]

    def validate_email(self, value: str) -> str:
        val = value.strip().lower()
        qs = User.objects.filter(email__iexact=val)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Email đã tồn tại.")
        return val

    def create(self, validated_data):
        roles = ensure_default_roles()
        role_code = validated_data.pop("role_code", Role.CUSTOMER)
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "Mật khẩu là bắt buộc khi tạo tài khoản mới."})
        validate_password(password)
        user = User.objects.create_user(
            role=roles[role_code],
            password=password,
            **validated_data,
        )
        return user

    def update(self, instance, validated_data):
        roles = ensure_default_roles()
        role_code = validated_data.pop("role_code", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if role_code:
            instance.role = roles[role_code]
        if password:
            validate_password(password, instance)
            instance.set_password(password)
        instance.save()
        return instance
