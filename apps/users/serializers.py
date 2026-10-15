from django.contrib.auth import get_user_model, password_validation
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .roles import ROLE_NAMES, get_role_name

User = get_user_model()


class UserReadSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "is_active", "role")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_role(self, obj):
        return get_role_name(obj)


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=ROLE_NAMES)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value

    def validate(self, attrs):
        candidate = User(username=attrs.get("username"))
        password_validation.validate_password(attrs["password"], candidate)
        return attrs


class RoleAssignmentSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ROLE_NAMES)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)
