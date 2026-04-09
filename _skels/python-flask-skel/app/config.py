"""Application configuration.

Loads the wrapper-shared ``.env`` first so DATABASE_URL / JWT_SECRET are
inherited from the project root, then the local service ``.env`` for
service-specific overrides.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
_WRAPPER_ENV = _BASE_DIR.parent / ".env"
if _WRAPPER_ENV.is_file():
    load_dotenv(_WRAPPER_ENV)
load_dotenv(_BASE_DIR / ".env")


def _resolve_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    wrapper_dir = _BASE_DIR.parent
    shared_default = wrapper_dir / "_shared" / "db.sqlite3"

    if raw.startswith("sqlite:///"):
        path = wrapper_dir / raw[len("sqlite:///"):]
        return f"sqlite:///{path}"
    if raw:
        return raw
    if shared_default.is_file():
        return f"sqlite:///{shared_default}"
    return "sqlite:///app.db"


class Config:
    """Base configuration."""

    # Shared JWT material (interchangeable across every service in the wrapper).
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-32-bytes-of-random-data")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ISSUER = os.getenv("JWT_ISSUER", "devskel")
    JWT_ACCESS_TTL = int(os.getenv("JWT_ACCESS_TTL", "3600"))
    JWT_REFRESH_TTL = int(os.getenv("JWT_REFRESH_TTL", "604800"))

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or JWT_SECRET
    SQLALCHEMY_DATABASE_URI = _resolve_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    """Test configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
