"""
Django settings for myproject.

Loads the wrapper-level ``.env`` first (so DATABASE_URL / JWT_SECRET are
inherited from the project root) and then the local service ``.env`` for
service-specific overrides.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

WRAPPER_ENV = BASE_DIR.parent / ".env"
if WRAPPER_ENV.is_file():
    load_dotenv(WRAPPER_ENV)
load_dotenv(BASE_DIR / ".env")

# Shared JWT secret + algorithm so tokens are interchangeable between
# services in the same wrapper.
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-32-bytes-of-random-data")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "devskel")
JWT_ACCESS_TTL = int(os.getenv("JWT_ACCESS_TTL", "3600"))
JWT_REFRESH_TTL = int(os.getenv("JWT_REFRESH_TTL", "604800"))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or JWT_SECRET

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"

# Database — DATABASE_URL from the wrapper-shared .env wins; falls back to
# the shared SQLite file at <wrapper>/_shared/db.sqlite3 (created by
# common-wrapper.sh) and finally to a local sqlite for stand-alone use.
def _build_databases() -> dict:
    url = os.environ.get("DATABASE_URL", "").strip()
    wrapper_dir = BASE_DIR.parent
    shared_default = wrapper_dir / "_shared" / "db.sqlite3"
    local_default = BASE_DIR / "db.sqlite3"

    if url and url.startswith("sqlite:///"):
        relative = url[len("sqlite:///"):]
        path = wrapper_dir / relative
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(path)}}

    if url and url.startswith("postgres"):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return {"default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": (parsed.path or "/postgres").lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }}

    if shared_default.is_file():
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(shared_default)}}
    return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(local_default)}}


DATABASES = _build_databases()

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
