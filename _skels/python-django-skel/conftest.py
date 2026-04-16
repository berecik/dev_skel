"""Pytest configuration.

Settings come from ``myproject.settings`` (configured in
``pyproject.toml``'s ``[tool.pytest.ini_options]``). pytest-django
handles `django.setup()` automatically — we just need to override
the database to an in-memory SQLite so tests don't touch the
wrapper-shared file.
"""

import os

# Force the in-memory SQLite for tests BEFORE settings are imported.
os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")
os.environ.setdefault("DJANGO_DEBUG", "True")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "*")
