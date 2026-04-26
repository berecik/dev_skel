"""URL routes for the wrapper-shared backend stack."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.views import (
    CatalogDetailView,
    CatalogListCreateView,
    CategoryViewSet,
    ItemViewSet,
    LoginView,
    OrderAddressView,
    OrderApproveView,
    OrderDetailView,
    OrderLineCreateView,
    OrderLineDeleteView,
    OrderListCreateView,
    OrderRejectView,
    OrderSubmitView,
    RegisterView,
    StateKeyView,
    StateView,
)

router = DefaultRouter(trailing_slash=False)
router.register(r"categories", CategoryViewSet, basename="categories")
router.register(r"items", ItemViewSet, basename="items")

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("state", StateView.as_view(), name="state-list"),
    path("state/<path:key>", StateKeyView.as_view(), name="state-key"),
    # Order workflow
    path("catalog", CatalogListCreateView.as_view(), name="catalog-list-create"),
    path("catalog/<int:pk>", CatalogDetailView.as_view(), name="catalog-detail"),
    path("orders", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<int:pk>", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:pk>/lines", OrderLineCreateView.as_view(), name="order-line-create"),
    path("orders/<int:pk>/lines/<int:line_id>", OrderLineDeleteView.as_view(), name="order-line-delete"),
    path("orders/<int:pk>/address", OrderAddressView.as_view(), name="order-address"),
    path("orders/<int:pk>/submit", OrderSubmitView.as_view(), name="order-submit"),
    path("orders/<int:pk>/approve", OrderApproveView.as_view(), name="order-approve"),
    path("orders/<int:pk>/reject", OrderRejectView.as_view(), name="order-reject"),
    path("", include(router.urls)),
]
