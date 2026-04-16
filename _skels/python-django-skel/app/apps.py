"""App config for the wrapper-shared backend stack."""

from django.apps import AppConfig


class AppConfig(AppConfig):
    """Django app config — registered as ``app`` in INSTALLED_APPS."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app"
    label = "app"
