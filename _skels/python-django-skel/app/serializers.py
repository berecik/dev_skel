"""DRF serializers for the wrapper-shared backend stack."""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from app.models import (
    CatalogItem,
    Category,
    Item,
    Order,
    OrderAddress,
    OrderLine,
)


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


class CategorySerializer(serializers.ModelSerializer):
    """Wrapper-shared category resource."""

    class Meta:
        model = Category
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class CategoryCreateSerializer(serializers.ModelSerializer):
    """Payload for ``POST /api/categories`` and ``PUT /api/categories/{id}``."""

    class Meta:
        model = Category
        fields = ("name", "description")
        extra_kwargs = {
            "description": {"required": False, "allow_null": True, "allow_blank": True},
        }


class ItemSerializer(serializers.ModelSerializer):
    """Snake_case JSON for the React frontend."""

    class Meta:
        model = Item
        fields = ("id", "name", "description", "is_completed", "category_id", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ItemCreateSerializer(serializers.ModelSerializer):
    """Loose validation for create — `is_completed` defaults to False."""

    category_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    class Meta:
        model = Item
        fields = ("name", "description", "is_completed", "category_id")
        extra_kwargs = {
            "description": {"required": False, "allow_null": True, "allow_blank": True},
            "is_completed": {"required": False, "default": False},
        }


class StateUpsertSerializer(serializers.Serializer):
    """Payload for ``PUT /api/state/<key>`` — value is an opaque JSON string."""

    value = serializers.CharField(allow_blank=True, trim_whitespace=False)


# --------------------------------------------------------------------------- #
#  Order workflow serializers
# --------------------------------------------------------------------------- #


class CatalogItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogItem
        fields = ("id", "name", "description", "price", "category", "available")
        read_only_fields = ("id",)


class CatalogItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogItem
        fields = ("name", "description", "price", "category", "available")
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "category": {"required": False, "allow_blank": True},
            "available": {"required": False},
        }


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = ("id", "catalog_item_id", "quantity", "unit_price")
        read_only_fields = ("id",)


class OrderAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderAddress
        fields = ("street", "city", "zip_code", "phone", "notes")
        extra_kwargs = {
            "phone": {"required": False, "allow_blank": True},
            "notes": {"required": False, "allow_blank": True},
        }


class OrderDetailSerializer(serializers.ModelSerializer):
    """Full order with nested lines and address."""

    lines = OrderLineSerializer(many=True, read_only=True)
    address = OrderAddressSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "user_id", "status", "created_at", "submitted_at",
            "wait_minutes", "feedback", "lines", "address",
        )
        read_only_fields = ("id", "user_id", "status", "created_at", "submitted_at")


class OrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "user_id", "status", "created_at", "submitted_at")
