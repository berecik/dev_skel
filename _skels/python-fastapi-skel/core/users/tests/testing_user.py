from core.tests.utils import FakeRepository
from core.users.db import UserRepository, UserUnitOfWork, UserCrud
from core.users.models import UserBase
user_create_data = dict(email="test@nazwa.pl", password="test")


class UserBaseTest(UserBase):
    hashed_password: str


class UserRepositoryTest(FakeRepository[UserBaseTest], UserRepository):
    ...


class UserUnitOfWorkTest(UserUnitOfWork):

    def __init__(self):
        super().__init__(UserBaseTest, UserCrud, repository=UserRepositoryTest)

    def rollback(self):
        pass

    def _commit(self):
        pass

    repository_type = UserRepositoryTest