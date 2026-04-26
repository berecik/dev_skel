"""`/api/auth/register` and `/api/auth/login` endpoints.

Both endpoints accept JSON bodies (NOT form data) and return shapes
compatible with the django-bolt skel:

* register → `{user: {id, username, email}}` with status 201
* login → `{access, refresh, user_id, username}` with status 200

That way the React skel's `src/api/items.ts::loginWithPassword` flow
works against either backend without any code changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from .db import WrapperUser
from .deps import SessionDep
from .schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    RegisterUser,
)
from .security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["wrapper-auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
def register(payload: RegisterRequest, session: SessionDep) -> RegisterResponse:
    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing = session.exec(
        select(WrapperUser).where(WrapperUser.username == payload.username)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = WrapperUser(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return RegisterResponse(
        user=RegisterUser(id=user.id, username=user.username, email=user.email)
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: SessionDep) -> LoginResponse:
    # Allow login by email when the submitted value contains "@".
    if "@" in payload.username:
        stmt = select(WrapperUser).where(WrapperUser.email == payload.username)
    else:
        stmt = select(WrapperUser).where(WrapperUser.username == payload.username)
    user = session.exec(stmt).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return LoginResponse(
        access=create_access_token(user.id),
        refresh=create_refresh_token(user.id),
        user_id=user.id,
        username=user.username,
    )
