from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder

from core.deps import (
    CurrentUser,
    UsersDep,
    get_current_active_superuser,
)
from .. import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserUpdateMe,
)

import config

router = APIRouter()


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=List[UserBase],
)
def read_users(users: UsersDep) -> Any:
    """
    Retrieve users.
    """
    return users.list()


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserBase
)
def create_user(*, users: UsersDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    try:
        user = users.create(user_in)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    return user


@router.put("/me", response_model=UserBase)
def update_user_me(
        *, users: UsersDep, body: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """
    current_user_data = jsonable_encoder(current_user)
    user_in = UserUpdate(**current_user_data)
    if body.password is not None:
        user_in.password = body.password
    if body.full_name is not None:
        user_in.full_name = body.full_name
    if body.email is not None:
        user_in.email = body.email

    user = users.update(id=current_user.id, obj_in=user_in)
    return user


@router.get("/me", response_model=UserBase)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.post("/open", response_model=UserBase)
def create_user_open(users: UsersDep, user_in: UserCreate) -> Any:
    """
    Create new user without the need to be logged in.
    """
    if not config.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open user registration is forbidden on this server",
        )
    user = users.get_user_by_email(email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    user = users.create(user_in)
    return user


@router.get("/{user_id}", response_model=UserBase)
def read_user_by_id(
        user_id: int, users: UsersDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """

    user = users.get(user_id)
    if user == current_user:
        return user
    if current_user.is_superuser:
        return user
    raise HTTPException(
        status_code=400,
        detail="The user doesn't have enough privileges",
    )


@router.put(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserBase,
)
def update_user(
        *,
        users: UsersDep,
        user_id: int,
        user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    user = users.get(user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system",
        )
    user = users.update(id=user_id, obj_in=user_in)
    return user


@router.delete(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserBase,
)
def update_user(
        *,
        users: UsersDep,
        user_id: int,
) -> Any:
    """
    Update a user.
    """

    user = users.get(user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system",
        )
    user = users.remove(id=user_id)
    return user
