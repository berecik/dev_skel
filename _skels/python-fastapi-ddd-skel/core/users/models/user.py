from abc import ABC
from typing import Optional, Any, Union, Dict, Type

from pydantic import BaseModel, EmailStr

from core.unit_of_work import AbstractUnitOfWork
from core.crud import CRUDBase
from core.repository import AbstractRepository
from core.security import get_password_hash, verify_password


# Shared properties
class UserBase(BaseModel):
    id: Optional[int] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    password: str


# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None


class UserUpdateMe(BaseModel):
    password: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class NewPassword(BaseModel):
    token: str
    new_password: str


class UserRepository(AbstractRepository, ABC):
    model: Type[UserBase]

    def filter_by_email(self, email: str) -> Optional[UserBase]:
        try:
            return filter(lambda user: user.email == email, self.list()).__next__()
        except StopIteration:
            return None


class UserCrud(CRUDBase[UserBase, UserCreate, UserUpdate]):
    repository: UserRepository

    def get_by_email(self, email: str) -> Optional[UserBase]:
        return self.repository.filter_by_email(email=email)

    def create(self, obj_in: UserCreate, update_if_exist=False) -> UserBase:
        user = self.get_by_email(email=obj_in.email)
        if user:
            if update_if_exist:
                return self.update(id=user.id, obj_in=obj_in)
            else:
                raise ValueError("User already exists")

        db_obj = self.repository.model(
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
            is_active=obj_in.is_active,
        )
        self.repository.add(db_obj)
        return db_obj

    def update(
            self, id: int, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> UserBase:
        db_obj = self.get(id=id)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        if update_data.get("password", False):
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        return super()._update(db_obj=db_obj, obj_in=update_data)

    def authenticate(self, email: str, password: str) -> Optional[UserBase]:
        user = self.get_by_email(email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


class UserUnitOfWork(AbstractUnitOfWork[UserCrud], ABC):
    repository_type = UserRepository
    crud_type = UserCrud
    model_type = UserBase
