"""DRF views for the wrapper-shared HTTP contract."""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from app.models import (
    CatalogItem,
    Category,
    Item,
    Order,
    OrderAddress,
    OrderLine,
    ReactState,
)
from app.serializers import (
    CatalogItemCreateSerializer,
    CatalogItemSerializer,
    CategoryCreateSerializer,
    CategorySerializer,
    ItemCreateSerializer,
    ItemSerializer,
    OrderAddressSerializer,
    OrderDetailSerializer,
    OrderLineSerializer,
    OrderListSerializer,
    RegisterSerializer,
    StateUpsertSerializer,
    UserOutSerializer,
)


def _tokens_for_user(user: User) -> dict[str, str]:
    """Mint the (access, refresh) pair for ``user``.

    Centralised here so register + login produce the same shape and
    so any future tweak (e.g. extra claims) lives in one place.
    """

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class RegisterView(APIView):
    """POST /api/auth/register → 201 ``{user, access, refresh}``."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            # Distinguish duplicate-username from generic validation
            # so the React client can show the right error.
            errors = serializer.errors
            username_errors = errors.get("username", [])
            if any("already exists" in str(e) for e in username_errors):
                return Response(
                    {"detail": str(username_errors[0]), "status": status.HTTP_409_CONFLICT},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {"detail": _flatten_errors(errors), "status": status.HTTP_400_BAD_REQUEST},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        body = {"user": UserOutSerializer(user).data, **_tokens_for_user(user)}
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login → 200 ``{access, refresh, user_id, username}``."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return _unauth("invalid username or password")
        if "@" in username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user_obj = User.objects.get(email=username)
            except User.DoesNotExist:
                return _unauth("invalid username or password")
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            return _unauth("invalid username or password")
        body = {
            **_tokens_for_user(user),
            "user_id": user.id,
            "username": user.username,
        }
        return Response(body, status=status.HTTP_200_OK)


class CategoryViewSet(viewsets.ModelViewSet):
    """``/api/categories`` CRUD — JWT-protected.

    Categories are wrapper-shared and not scoped to any user.
    """

    queryset = Category.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CategoryCreateSerializer
        return CategorySerializer

    def create(self, request, *args, **kwargs):
        serializer = CategoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(CategorySerializer(category).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = CategoryCreateSerializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(CategorySerializer(category).data, status=status.HTTP_200_OK)


class ItemViewSet(viewsets.ModelViewSet):
    """``/api/items`` CRUD — JWT-protected, snake_case JSON.

    Items are intentionally NOT scoped to the calling user (matches
    the django-bolt convention so cross-stack tests can pre-seed via
    raw SQL and every backend in the wrapper sees the same data).
    """

    queryset = Item.objects.all()
    permission_classes = [IsAuthenticated]
    # /api/items returns plain `[]` (not `{count, results}`) because
    # the React client expects an array. Disable pagination here
    # explicitly even if a project enables it globally later.
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "create":
            return ItemCreateSerializer
        return ItemSerializer

    def create(self, request, *args, **kwargs):
        # Reuse the create serializer for validation but return the
        # full ItemSerializer body (so the React client gets `id`,
        # `created_at`, `updated_at` back).
        serializer = ItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(ItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Idempotent flip of ``is_completed`` to True."""

        item = self.get_object()
        if not item.is_completed:
            item.is_completed = True
            item.save(update_fields=["is_completed", "updated_at"])
        return Response(ItemSerializer(item).data, status=status.HTTP_200_OK)


class StateView(APIView):
    """GET /api/state — return ``{key: value}`` for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = ReactState.objects.filter(user=request.user).order_by("key")
        return Response({row.key: row.value for row in rows}, status=status.HTTP_200_OK)


class StateKeyView(APIView):
    """PUT/DELETE /api/state/<key> — upsert / delete a slice."""

    permission_classes = [IsAuthenticated]

    def put(self, request, key: str):
        serializer = StateUpsertSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": _flatten_errors(serializer.errors), "status": status.HTTP_400_BAD_REQUEST},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ReactState.objects.update_or_create(
            user=request.user, key=key,
            defaults={"value": serializer.validated_data["value"]},
        )
        return Response({"key": key}, status=status.HTTP_200_OK)

    def delete(self, request, key: str):
        ReactState.objects.filter(user=request.user, key=key).delete()
        return Response({}, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------- #
#  Order workflow views
# --------------------------------------------------------------------------- #


class CatalogListCreateView(APIView):
    """GET /api/catalog — list all catalog items.
    POST /api/catalog — create a new catalog item.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = CatalogItem.objects.all().order_by("id")
        return Response(CatalogItemSerializer(items, many=True).data)

    def post(self, request):
        serializer = CatalogItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(CatalogItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CatalogDetailView(APIView):
    """GET /api/catalog/{id} — retrieve a single catalog item."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            item = CatalogItem.objects.get(pk=pk)
        except CatalogItem.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(CatalogItemSerializer(item).data)


class OrderListCreateView(APIView):
    """POST /api/orders — create a draft order for the current user.
    GET  /api/orders — list the current user's orders.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        order = Order.objects.create(user=request.user, status="draft")
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)

    def get(self, request):
        orders = Order.objects.filter(user=request.user).order_by("-created_at")
        return Response(OrderListSerializer(orders, many=True).data)


class OrderDetailView(APIView):
    """GET /api/orders/{id} — order detail with nested lines + address."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = Order.objects.prefetch_related("lines").select_related("address").get(
                pk=pk, user=request.user,
            )
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderDetailSerializer(order).data)


class OrderLineCreateView(APIView):
    """POST /api/orders/{id}/lines — add a line to a draft order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if order.status != "draft":
            return Response(
                {"detail": "can only add lines to draft orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        catalog_item_id = request.data.get("catalog_item_id")
        quantity = request.data.get("quantity", 1)
        try:
            catalog_item = CatalogItem.objects.get(pk=catalog_item_id)
        except CatalogItem.DoesNotExist:
            return Response({"detail": "catalog item not found"}, status=status.HTTP_404_NOT_FOUND)
        line = OrderLine.objects.create(
            order=order,
            catalog_item=catalog_item,
            quantity=quantity,
            unit_price=catalog_item.price,
        )
        return Response(OrderLineSerializer(line).data, status=status.HTTP_201_CREATED)


class OrderLineDeleteView(APIView):
    """DELETE /api/orders/{id}/lines/{line_id} — remove a line from a draft order."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, line_id):
        try:
            order = Order.objects.get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if order.status != "draft":
            return Response(
                {"detail": "can only remove lines from draft orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = OrderLine.objects.filter(pk=line_id, order=order).delete()
        if not deleted:
            return Response({"detail": "line not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({}, status=status.HTTP_200_OK)


class OrderAddressView(APIView):
    """PUT /api/orders/{id}/address — set or update the order address."""

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderAddressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        OrderAddress.objects.update_or_create(
            order=order,
            defaults=serializer.validated_data,
        )
        return Response(OrderAddressSerializer(OrderAddress.objects.get(order=order)).data)


class OrderSubmitView(APIView):
    """POST /api/orders/{id}/submit — transition draft -> pending."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if order.status != "draft":
            return Response(
                {"detail": "only draft orders can be submitted"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.utils import timezone

        order.status = "pending"
        order.submitted_at = timezone.now()
        order.save(update_fields=["status", "submitted_at"])
        return Response(OrderDetailSerializer(order).data)


class OrderApproveView(APIView):
    """POST /api/orders/{id}/approve — approve a pending order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if order.status != "pending":
            return Response(
                {"detail": "only pending orders can be approved"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = "approved"
        order.wait_minutes = request.data.get("wait_minutes")
        order.feedback = request.data.get("feedback", "")
        order.save(update_fields=["status", "wait_minutes", "feedback"])
        return Response(OrderDetailSerializer(order).data)


class OrderRejectView(APIView):
    """POST /api/orders/{id}/reject — reject a pending order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        if order.status != "pending":
            return Response(
                {"detail": "only pending orders can be rejected"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = "rejected"
        order.feedback = request.data.get("feedback", "")
        order.save(update_fields=["status", "feedback"])
        return Response(OrderDetailSerializer(order).data)


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def _unauth(detail: str) -> Response:
    return Response(
        {"detail": detail, "status": status.HTTP_401_UNAUTHORIZED},
        status=status.HTTP_401_UNAUTHORIZED,
    )


def _flatten_errors(errors) -> str:
    """Turn DRF's nested error dict into a single human-readable string."""

    if isinstance(errors, list):
        return "; ".join(str(e) for e in errors)
    if isinstance(errors, dict):
        parts = []
        for field, msgs in errors.items():
            if isinstance(msgs, list):
                parts.append(f"{field}: {'; '.join(str(m) for m in msgs)}")
            else:
                parts.append(f"{field}: {msgs}")
        return "; ".join(parts)
    return str(errors)
