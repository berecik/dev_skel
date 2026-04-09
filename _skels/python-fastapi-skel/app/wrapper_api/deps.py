"""FastAPI dependency providers for the wrapper-shared API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import Session, select

from .db import WrapperUser, get_session
from .security import decode_token

# Use HTTPBearer rather than OAuth2PasswordBearer because the React skel
# sends JSON `{username, password}` to `/api/auth/login` and expects an
# `Authorization: Bearer <token>` header on every subsequent request.
# OAuth2PasswordBearer would also work but it forces the OpenAPI form
# UI to use form-encoded login, which we do not want.
_bearer = HTTPBearer(auto_error=True)

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_wrapper_user(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> WrapperUser:
    try:
        payload = decode_token(creds.credentials)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is not a numeric user id",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = session.exec(
        select(WrapperUser).where(WrapperUser.id == user_id)
    ).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[WrapperUser, Depends(get_current_wrapper_user)]
