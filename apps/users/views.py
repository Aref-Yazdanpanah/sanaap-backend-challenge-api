from django.contrib.auth import get_user_model
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .permissions import IsDMSAdmin
from .serializers import (
    LogoutSerializer,
    RoleAssignmentSerializer,
    UserCreateSerializer,
    UserReadSerializer,
)
from .services import change_role, create_user, profile_cache_key

User = get_user_model()


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired refresh token."}, status=400)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.prefetch_related("groups").order_by("username", "id")
    permission_classes = [IsAuthenticated, IsDMSAdmin]

    def get_serializer_class(self):
        return {
            "create": UserCreateSerializer,
            "set_role": RoleAssignmentSerializer,
        }.get(self.action, UserReadSerializer)

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(UserReadSerializer(page, many=True).data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = create_user(**serializer.validated_data)
        return Response(UserReadSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="role")
    def set_role(self, request, pk=None):
        user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = change_role(user=user, role=serializer.validated_data["role"])
        return Response(UserReadSerializer(user).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        key = profile_cache_key(request.user.pk)
        data = cache.get(key)
        if data is None:
            user = User.objects.prefetch_related("groups").get(pk=request.user.pk)
            data = UserReadSerializer(user).data
            cache.set(key, data, timeout=60)
        return Response(data)
