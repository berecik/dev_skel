import sys
import os
import logging

from loguru import logger
from starlette.config import Config
from starlette.datastructures import Secret

from core.common_logging import InterceptHandler

try:
    config = Config(".env")
except Exception as e:
    config = Config()

CORE_API_PREFIX = ""
USER_API_PREFIX = "/user"

DEBUG: bool = config("DEBUG", cast=bool, default=False)
MAX_CONNECTIONS_COUNT: int = config("MAX_CONNECTIONS_COUNT", cast=int, default=10)
MIN_CONNECTIONS_COUNT: int = config("MIN_CONNECTIONS_COUNT", cast=int, default=10)
SECRET_KEY: Secret = config("SECRET_KEY", cast=Secret, default=Secret("CHANGEME"))

# logging configuration
LOGGING_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    handlers=[InterceptHandler(level=LOGGING_LEVEL)], level=LOGGING_LEVEL
)
logger.configure(handlers=[{"sink": sys.stderr, "level": LOGGING_LEVEL}])

SQLALCHEMY_DATABASE_URI = config("DATABASE_URL", default="sqlite:///./test.db")
SQLALCHEMY_DATABASE_TEST_URI = config("DATABASE_TEST_URL", default=SQLALCHEMY_DATABASE_URI)

API_PREFIX = CORE_API_PREFIX
DEBUG = False

EMAIL_TEMPLATES_DIR = config("EMAIL_TEMPLATES_DIR", default=f"{os.path.dirname(__file__)}/email-templates")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 8  # one week
