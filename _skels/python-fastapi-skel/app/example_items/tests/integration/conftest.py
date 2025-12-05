import pytest
from sqlalchemy.orm import Session

from app.example_items.adapters.sql import ExampleItemSqlUnitOfWork, ExampleItem, get_example_item_uow
from app.example_items.models import ExampleItemUnitOfWork, ExampleItemCrud
from core.users import UserUnitOfWork, UserCrud
from core.users.db import UserSqlUnitOfWork, User


@pytest.fixture(name="users_uow")
def users_uow_fixture(session: Session) -> UserUnitOfWork:
    def session_factory() -> Session:
        return session

    yield UserSqlUnitOfWork(User, UserCrud, session_factory=session_factory)


@pytest.fixture(name="example_items_uow")
def example_items_uow_fixture(session: Session) -> ExampleItemUnitOfWork:
    def session_factory() -> Session:
        return session

    yield ExampleItemSqlUnitOfWork(ExampleItem, ExampleItemCrud, session_factory=session_factory)


@pytest.fixture(name="app_dependencies")
def get_app_dependencies(example_items_uow: ExampleItemUnitOfWork):
    def get_test_example_item_uow():
        return example_items_uow

    return [(get_example_item_uow, get_test_example_item_uow)]
