import logging
import os
import sys
from pathlib import Path

from loguru import logger
from starlette.config import Config
from starlette.datastructures import Secret

from core.common_logging import InterceptHandler

# Wrapper-shared environment is loaded first so DATABASE_URL / JWT_SECRET
# inherited from <wrapper>/.env are visible to every service. The local
# service `.env` is loaded second by starlette.config.Config so it overrides
# anything from the wrapper layer.
_BASE_DIR = Path(__file__).resolve().parent.parent
_WRAPPER_ENV = _BASE_DIR.parent / ".env"
if _WRAPPER_ENV.is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(_WRAPPER_ENV)
    except ImportError:  # pragma: no cover - dotenv ships with the skel
        pass

try:
    config = Config(".env")
except Exception:
    config = Config()

CORE_API_PREFIX = ""
USER_API_PREFIX = "/user"

DEBUG: bool = config("DEBUG", cast=bool, default=False)
MAX_CONNECTIONS_COUNT: int = config("MAX_CONNECTIONS_COUNT", cast=int, default=10)
MIN_CONNECTIONS_COUNT: int = config("MIN_CONNECTIONS_COUNT", cast=int, default=10)

# JWT material — shared with every service in the wrapper. SECRET_KEY is an
# alias kept for backwards compatibility with code that still imports the
# old name.
JWT_SECRET: Secret = config(
    "JWT_SECRET", cast=Secret, default=Secret("change-me-32-bytes-of-random-data")
)
JWT_ALGORITHM: str = config("JWT_ALGORITHM", default="HS256")
JWT_ISSUER: str = config("JWT_ISSUER", default="devskel")
JWT_ACCESS_TTL: int = config("JWT_ACCESS_TTL", cast=int, default=3600)
JWT_REFRESH_TTL: int = config("JWT_REFRESH_TTL", cast=int, default=604800)
SECRET_KEY = JWT_SECRET

# logging configuration
LOGGING_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    handlers=[InterceptHandler(level=LOGGING_LEVEL)], level=LOGGING_LEVEL
)
logger.configure(handlers=[{"sink": sys.stderr, "level": LOGGING_LEVEL}])


def _resolve_database_url() -> str:
    """Pick a database URL: explicit env var > shared sqlite > local sqlite.

    SQLite paths in the shared ``DATABASE_URL`` are interpreted relative to
    the wrapper directory so the same value works for every service.
    """

    raw = config("DATABASE_URL", default="").strip()
    wrapper_dir = _BASE_DIR.parent
    shared_default = wrapper_dir / "_shared" / "db.sqlite3"

    if raw.startswith("sqlite:///"):
        path = wrapper_dir / raw[len("sqlite:///"):]
        return f"sqlite:///{path}"
    if raw:
        return raw
    if shared_default.is_file():
        return f"sqlite:///{shared_default}"
    return f"sqlite:///{_BASE_DIR / 'test.db'}"


SQLALCHEMY_DATABASE_URI = _resolve_database_url()
SQLALCHEMY_DATABASE_TEST_URI = config(
    "DATABASE_TEST_URL", default=SQLALCHEMY_DATABASE_URI
)

API_PREFIX = CORE_API_PREFIX
DEBUG = False

EMAIL_TEMPLATES_DIR = config(
    "EMAIL_TEMPLATES_DIR", default=f"{os.path.dirname(__file__)}/email-templates"
)
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TTL // 60
