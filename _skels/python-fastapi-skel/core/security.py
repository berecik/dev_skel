"""JWT helpers backed by the wrapper-shared secret.

Tokens issued here are interchangeable with tokens issued by every other
service in the same wrapper because they all source the same secret /
algorithm / issuer from the shared environment.
"""

from datetime import datetime, timedelta
from typing import Any, Union

from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext

from core import config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(seconds=config.JWT_ACCESS_TTL)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iss": config.JWT_ISSUER,
    }
    return jwt.encode(
        to_encode,
        str(config.JWT_SECRET),
        algorithm=config.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """Verify a JWT against the shared secret and return its payload."""

    return jwt.decode(
        token,
        str(config.JWT_SECRET),
        algorithms=[config.JWT_ALGORITHM],
        issuer=config.JWT_ISSUER,
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)