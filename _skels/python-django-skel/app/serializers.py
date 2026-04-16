"""DRF serializers for the wrapper-shared backend stack."""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from app.models import Item


class UserOutSerializer(serializers.ModelSerializer):
    """Serialise a ``User`` for register / login responses."""

    class Meta:
        model = User
        fields = ("id", "username", "email")


class RegisterSerializer(serializers.Serializer):
    """Payload for ``POST /api/auth/register``.

    Accepts the optional ``password_confirm`` field the React client
    sends and validates it server-side.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default=""
    )

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(f"user '{value}' already exists")
        return value

    def validate(self, attrs: dict) -> dict:
        confirm = attrs.get("password_confirm") or ""
        if confirm and confirm != attrs["password"]:
            raise serializers.ValidationError(
                {"password_confirm": "password and password_confirm do not match"}
            )
        # Run Django's standard password validators so we surface
        # weak-password errors with the same messages the admin uses.
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class ItemSerializer(serializers.ModelSerializer):
    """Snake_case JSON for the React frontend."""

    class Meta:
        model = Item
        fields = ("id", "name", "description", "is_completed", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ItemCreateSerializer(serializers.ModelSerializer):
    """Loose validation for create — `is_completed` defaults to False."""

    class Meta:
        model = Item
        fields = ("name", "description", "is_completed")
        extra_kwargs = {
            "description": {"required": False, "allow_null": True, "allow_blank": True},
            "is_completed": {"required": False, "default": False},
        }


class StateUpsertSerializer(serializers.Serializer):
    """Payload for ``PUT /api/state/<key>`` — value is an opaque JSON string."""

    value = serializers.CharField(allow_blank=True, trim_whitespace=False)
