from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

import config
from core.deps import CurrentUser, UsersDep, CurrentSuperUser
from core.security import get_password_hash, create_access_token
from core.users import Msg, Token, UserBase, NewPassword
from ..utils import (
    generate_password_reset_token,
    send_reset_password_email,
    verify_password_reset_token,
)

router = APIRouter()


@router.post("/login/access-token")
def login_access_token(
    users: UsersDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """

    user = users.authenticate(
        email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )
    return Token(
        access_token=access_token, token_type="bearer"
    )


@router.post("/login/test-token", response_model=UserBase)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/login/test-supertoken", response_model=UserBase)
def test_supertoken(current_user: CurrentSuperUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, users: UsersDep) -> Msg:
    """
    Password Recovery
    """
    user = users.get_user_by_email(email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    send_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    return Msg(msg="Password recovery email sent")


@router.post("/reset-password/")
def reset_password(user_uow: UsersDep, body: NewPassword) -> Msg:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    with user_uow as users:
        user = users.get_user_by_email(email=email)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="The user with this username does not exist in the system.",
            )
        elif not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        hashed_password = get_password_hash(password=body.new_password)
        user.hashed_password = hashed_password
        users.add(user)
        user_uow.commit()
    return Msg(msg="Password updated successfully")
