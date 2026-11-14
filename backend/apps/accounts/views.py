import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PasswordResetToken, Role, User
from .permissions import IsAdmin, UserManagementPermission
from .serializers import (
    AdminUserWriteSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    UserDetailSerializer,
    UserMinimalSerializer,
    ensure_default_roles,
)

logger = logging.getLogger(__name__)


def _issue_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserDetailSerializer(user).data,
    }


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_issue_tokens_for_user(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        return Response(_issue_tokens_for_user(user), status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        return Response({"detail": "Đăng xuất thành công."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserDetailSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"detail": "Mật khẩu hiện tại không đúng."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Đổi mật khẩu thành công."})


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        response_payload = {
            "detail": "Nếu email tồn tại trong hệ thống, hướng dẫn đặt lại mật khẩu đã được tạo.",
        }

        if user:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            PasswordResetToken.objects.create(
                user=user,
                token_hash=token_hash,
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            logger.info("Password reset token generated for user_id=%s", user.id)
            if settings.DEBUG:
                response_payload["dev_reset_token"] = raw_token

        return Response(response_payload, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["token"].strip()
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        record = (
            PasswordResetToken.objects.select_related("user")
            .filter(token_hash=token_hash, used_at__isnull=True, expires_at__gt=timezone.now())
            .first()
        )
        if not record:
            return Response(
                {"detail": "Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = record.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        return Response({"detail": "Đặt lại mật khẩu thành công. Bạn có thể đăng nhập ngay."})


class RoleListView(generics.ListAPIView):
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        ensure_default_roles()
        return Role.objects.all()


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, UserManagementPermission]
    queryset = User.objects.select_related("role").all()

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        search = self.request.query_params.get("search")
        internal_only = self.request.query_params.get("internal_only")
        if role:
            qs = qs.filter(role__code=role)
        if internal_only in ("1", "true", "True"):
            qs = qs.exclude(role__code=Role.CUSTOMER)
        if search:
            qs = qs.filter(
                full_name__icontains=search
            ) | qs.filter(email__icontains=search) | qs.filter(username__icontains=search)
        return qs.distinct()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AdminUserWriteSerializer
        if self.request.user.role_code == Role.ADMIN:
            return UserDetailSerializer
        return UserMinimalSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserDetailSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsAdmin])
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response(
                {"detail": "Không thể tự vô hiệu hóa chính tài khoản đang đăng nhập."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response(UserDetailSerializer(user).data)
