"""JWT mint/verify + Flask decorator for ``Authorization: Bearer …``.

Token format matches every other dev_skel backend: HS256-signed,
``iss=devskel``, ``sub=<user_id>``, optional ``token_type=refresh``.
A token issued by django-bolt or fastapi is accepted here and vice
versa as long as the wrapper-shared ``JWT_SECRET`` matches.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable

import bcrypt
import jwt
from flask import current_app, g, jsonify, request

from app import db
from app.models import User


def _algorithm() -> str:
    """Normalise the configured algorithm — wrapper default is HS256."""

    algo = (current_app.config.get("JWT_ALGORITHM") or "HS256").upper()
    if algo not in {"HS256", "HS384", "HS512"}:
        return "HS256"
    return algo


def hash_password(password: str) -> str:
    """Return a bcrypt hash safe for storage."""

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """Compare ``password`` against the bcrypt ``stored_hash``."""

    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _mint(user_id: int, ttl_seconds: int, token_type: str | None) -> str:
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iss": current_app.config["JWT_ISSUER"],
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    if token_type is not None:
        payload["token_type"] = token_type
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm=_algorithm(),
    )


def mint_access_token(user_id: int) -> str:
    """Mint a short-lived access token (TTL = ``JWT_ACCESS_TTL``)."""

    return _mint(user_id, current_app.config["JWT_ACCESS_TTL"], None)


def mint_refresh_token(user_id: int) -> str:
    """Mint a long-lived refresh token (TTL = ``JWT_REFRESH_TTL``)."""

    return _mint(user_id, current_app.config["JWT_REFRESH_TTL"], "refresh")


def verify_token(token: str) -> dict[str, Any]:
    """Decode + verify a token. Raises ``jwt.PyJWTError`` on failure."""

    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=[_algorithm()],
        issuer=current_app.config["JWT_ISSUER"],
    )


def _unauthorized(detail: str):
    response = jsonify({"detail": detail, "status": 401})
    response.status_code = 401
    return response


def jwt_required(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that gates a route on a valid Bearer JWT.

    Sets ``flask.g.current_user`` to the authenticated :class:`User`
    instance for the duration of the request, mirroring the ``AuthUser``
    extractor pattern in the actix / axum / spring backends. Anonymous
    or invalid-token requests get a JSON ``{detail, status}`` 401 body
    matching the contract every other dev_skel backend honours.
    """

    @functools.wraps(handler)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return _unauthorized("missing or malformed Authorization header")
        token = header[len("Bearer "):].strip()
        try:
            claims = verify_token(token)
        except jwt.PyJWTError:
            return _unauthorized("invalid or expired token")
        if claims.get("token_type") == "refresh":
            return _unauthorized("refresh token cannot authenticate this request")
        try:
            user_id = int(claims["sub"])
        except (KeyError, TypeError, ValueError):
            return _unauthorized("malformed sub claim")

        user = db.session.get(User, user_id)
        if user is None:
            return _unauthorized("user no longer exists")
        g.current_user = user
        return handler(*args, **kwargs)

    return wrapped
