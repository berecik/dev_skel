"""URL routes for the wrapper-shared backend stack."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.views import (
    ItemViewSet,
    LoginView,
    RegisterView,
    StateKeyView,
    StateView,
)

router = DefaultRouter(trailing_slash=False)
router.register(r"items", ItemViewSet, basename="items")

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("state", StateView.as_view(), name="state-list"),
    path("state/<path:key>", StateKeyView.as_view(), name="state-key"),
    path("", include(router.urls)),
]
