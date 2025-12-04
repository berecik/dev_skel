"""Pytest configuration."""

import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for pytest."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
            ],
            ROOT_URLCONF="myproject.urls",
            SECRET_KEY="test-secret-key",
        )
    django.setup()
