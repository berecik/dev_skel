"""Django settings for the django-bolt skeleton service.

Reads the shared wrapper-level ``.env`` first (so ``DATABASE_URL``,
``JWT_SECRET`` and friends are inherited from the project root) and then
the local service ``.env`` for service-specific overrides. Both files are
optional; sane defaults keep the skeleton runnable on a bare clone.
"""

import os
from pathlib import Path

try:  # python-dotenv is in requirements.txt; degrade gracefully if missing.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is always installed in the skel
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent.parent

# Load wrapper-level .env first, then the local service .env so the local
# file always wins. Both are optional.
WRAPPER_ENV = BASE_DIR.parent / ".env"
if WRAPPER_ENV.is_file():
    load_dotenv(WRAPPER_ENV)
load_dotenv(BASE_DIR / ".env")

# JWT secret is shared across every service in the wrapper so a token
# minted by one is accepted by all the others. Falls back to JWT_SECRET if
# DJANGO_SECRET_KEY is not set, then to a dev fallback.
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-32-bytes-of-random-data")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.environ.get("JWT_ISSUER", "devskel")
JWT_ACCESS_TTL = int(os.environ.get("JWT_ACCESS_TTL", "3600"))
JWT_REFRESH_TTL = int(os.environ.get("JWT_REFRESH_TTL", "604800"))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or JWT_SECRET
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_bolt",
    "app",
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

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# Database — read from the shared DATABASE_URL when present so every
# backend service in the wrapper points at the same store. Falls back to a
# shared SQLite file at <wrapper>/_shared/db.sqlite3 (the file scaffolded
# by common-wrapper.sh), and finally to a local sqlite if the wrapper layer
# is not present (useful for in-place skeleton tests).
def _build_databases() -> dict:
    url = os.environ.get("DATABASE_URL", "").strip()
    wrapper_dir = BASE_DIR.parent
    shared_default = wrapper_dir / "_shared" / "db.sqlite3"
    local_default = BASE_DIR / "db.sqlite3"

    if url and url.startswith("sqlite:///"):
        # SQLite paths in DATABASE_URL are interpreted relative to the
        # wrapper directory so the same `.env` works for every service.
        relative = url[len("sqlite:///"):]
        path = wrapper_dir / relative
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(path)}}

    if url and url.startswith("postgres"):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
        except Exception:
            parsed = None
        if parsed and parsed.scheme:
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
