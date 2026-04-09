"""Pytest configuration for the django-bolt skeleton.

`pytest-django` reads `DJANGO_SETTINGS_MODULE` from this file so the test
suite can run from the project root without manually exporting the env var.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")


def pytest_configure(config) -> None:
    """Make sure Django is set up before any test imports the ORM."""

    import django

    django.setup()
