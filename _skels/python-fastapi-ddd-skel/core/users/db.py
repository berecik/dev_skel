from typing import Optional, Union
from sqlmodel import SQLModel, Field

from core.adapters.sql import SqlAlchemyRepository
from core.adapters.sql import SqlAlchemyUnitOfWork

from .models.user import UserBase, UserRepository, UserCrud, UserUnitOfWork


class User(UserBase, SQLModel, table=True):
    class Config:
        orm_mode = True

    id: Union[int, None] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str


class UserSqlRepository(UserRepository, SqlAlchemyRepository):
    def filter_by_email(self, email: str) -> Optional[UserBase]:
        return self._query().filter(self.model.email == email).first()


class UserSqlUnitOfWork(UserUnitOfWork, SqlAlchemyUnitOfWork):
    model_type = User
    repository_type = UserSqlRepository
    crud_type = UserCrud


def get_user_uow() -> UserUnitOfWork:
    return UserSqlUnitOfWork(User, UserCrud)
