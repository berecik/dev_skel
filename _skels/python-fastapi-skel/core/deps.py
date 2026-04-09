from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError

import config
from .users import TokenPayload, UserUnitOfWork
from .users.db import User, get_user_uow, UserCrud, UserBase
from . import security

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{config.CORE_API_PREFIX}/login/access-token"
)

UsersUowDep = Annotated[UserUnitOfWork, Depends(get_user_uow)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_users_crud(users_uow: UsersUowDep) -> UserUnitOfWork:
    with users_uow as users:
        yield users


UsersDep = Annotated[UserCrud, Depends(get_users_crud)]


def get_current_user(users: UsersDep, token: TokenDep) -> UserBase:
    try:
        payload = jwt.decode(
            token,
            str(config.JWT_SECRET),
            algorithms=[config.JWT_ALGORITHM],
            issuer=config.JWT_ISSUER,
        )
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    user = users.get(token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user


CurrentSuperUser = Annotated[User, Depends(get_current_active_superuser)]
