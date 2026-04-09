"""JWT helpers for the wrapper-shared API.

Token shape matches the django-bolt skel so a token issued by either
service is decode-compatible: HS256, `iss=devskel`, `sub=<user_id>`,
plus a `token_type` claim that distinguishes access from refresh.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import jwt
from passlib.context import CryptContext

import config


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iss": config.JWT_ISSUER,
        "iat": _now(),
        "exp": _now() + timedelta(seconds=config.JWT_ACCESS_TTL),
        "token_type": "access",
    }
    return jwt.encode(payload, str(config.JWT_SECRET), algorithm=config.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iss": config.JWT_ISSUER,
        "iat": _now(),
        "exp": _now() + timedelta(seconds=config.JWT_REFRESH_TTL),
        "token_type": "refresh",
    }
    return jwt.encode(payload, str(config.JWT_SECRET), algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode + verify against the wrapper-shared secret. Raises on failure."""

    return jwt.decode(
        token,
        str(config.JWT_SECRET),
        algorithms=[config.JWT_ALGORITHM],
        issuer=config.JWT_ISSUER,
    )
