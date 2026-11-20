from django.db.models import Count
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role, User
from .permissions import IsAdmin, UserManagementPermission
from .serializers import (
    AdminUserWriteSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    RoleSerializer,
    UserDetailSerializer,
    UserMinimalSerializer,
    ensure_default_roles,
)


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


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    pagination_class = None
    http_method_names = ["get", "patch", "put", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "features"):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        ensure_default_roles()
        return Role.objects.annotate(user_count=Count("users")).order_by("id")

    @action(detail=False, methods=["get"])
    def features(self, request):
        return Response(
            [
                {"key": key, "label": label, "description": desc}
                for key, label, desc in Role.FEATURE_MODULES
            ]
        )

    @action(detail=False, methods=["post"])
    def reset_defaults(self, request):
        ensure_default_roles()
        for role in Role.objects.all():
            role.permissions = list(Role.DEFAULT_PERMISSIONS.get(role.code, []))
            role.save(update_fields=["permissions"])
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)


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
            qs = (
                qs.filter(full_name__icontains=search)
                | qs.filter(email__icontains=search)
                | qs.filter(username__icontains=search)
            )
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
