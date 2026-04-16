from core.config import * # noqa

PROJECT_NAME: str = config("PROJECT_NAME", default="FastAPI RAG Project")
VERSION = "0.1.0"
API_PREFIX = "/api/v1"

# NOTE: do NOT re-define SQLALCHEMY_DATABASE_URI / SECRET_KEY here.
# `core.config` already resolves SQLALCHEMY_DATABASE_URI through
# `_resolve_database_url()` and exposes JWT_SECRET as the wrapper-shared
# signing secret.

SERVER_HOST = config("SERVER_HOST", default="http://localhost:8000")

USERS_OPEN_REGISTRATION = config("USERS_OPEN_REGISTRATION", default=False)

EMAILS_ENABLED = config("EMAILS_ENABLED", default=False)

EMAILS_FROM_NAME = config("EMAILS_FROM_NAME", default="FastAPI RAG")
EMAILS_FROM_EMAIL = config("EMAILS_FROM_EMAIL", default="noreply@example.com")
SMTP_HOST = config("SMTP_HOST", default=SERVER_HOST)
SMTP_TLS = config("SMTP_TLS", default=True)
SMTP_PORT = config("SMTP_PORT", default=587 if SMTP_TLS else 25)
SMTP_USER = config("SMTP_USER", default=EMAILS_FROM_EMAIL)
SMTP_PASSWORD = config("SMTP_PASSWORD", default="")

SUPERUSER_EMAIL = config("SUPERUSER_EMAIL", default="admin@example.com")
SUPERUSER_PASSWORD = config("SUPERUSER_PASSWORD", default="changeme")
SUPERUSER_FULL_NAME = config("SUPERUSER_FULL_NAME", default="Admin User")
