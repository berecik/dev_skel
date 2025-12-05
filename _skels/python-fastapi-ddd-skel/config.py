from core.config import * # noqa

PROJECT_NAME: str = config("PROJECT_NAME", default="Example Project")
VERSION = "0.1.0"
API_PREFIX = "/api/v1"

SQLALCHEMY_DATABASE_URI = config("DATABASE_URL", default="sqlite:///./example-project.db")
SQLALCHEMY_DATABASE_TEST_URI = config("DATABASE_TEST_URL", default="sqlite:///./test.db")
SECRET_KEY = config("SECRET_KEY", default="ala_ma_kota")

SERVER_HOST = config("SERVER_HOST", default="http://example-project.marysia.app:8000")

USERS_OPEN_REGISTRATION = config("USERS_OPEN_REGISTRATION", default=False)

EMAILS_ENABLED = config("EMAILS_ENABLED", default=False)

EMAILS_FROM_NAME = config("EMAILS_FROM_NAME", default="Example Project")
EMAILS_FROM_EMAIL = config("EMAILS_FROM_EMAIL", default="Example Author <example@hipisi.org.pl>")
SMTP_HOST = config("SMTP_HOST", default=SERVER_HOST)
SMTP_TLS = config("SMTP_TLS", default=True)
SMTP_PORT = config("SMTP_PORT", default=587 if SMTP_TLS else 25)
SMTP_USER = config("SMTP_USER", default=EMAILS_FROM_EMAIL)
SMTP_PASSWORD = config("SMTP_PASSWORD", default="")

## alrady defined in core/config.py:
# SQLALCHEMY_DATABASE_URI = config("DATABASE_URL", default= "sqlite:///./example-project.db")
# SECRET_KEY = config("SECRET_KEY", default= "ala_ma_kota")
##

SUPERUSER_EMAIL = config("SUPERUSER_EMAIL", default="example@hipisi.org.pl")
SUPERUSER_PASSWORD = config("SUPERUSER_PASSWORD", default="test")
SUPERUSER_FULL_NAME = config("SUPERUSER_FULL_NAME", default="Example Author")