import pytest

from app.depts import get_example_items_crud
from app.example_items.models import ExampleItemCreate, ExampleItemCrud
from core.users import UserBase

from core.tests import FakeRepository, FakeUnitOfWork

from app.example_items.models import ExampleItemBase, ExampleItemRepository, ExampleItemUnitOfWork


class ExampleItemRepositoryTest(FakeRepository[ExampleItemBase], ExampleItemRepository):
    ...


class ExampleItemUnitOfWorkTest(FakeUnitOfWork, ExampleItemUnitOfWork):
    repository_type = ExampleItemRepositoryTest


@pytest.fixture(name="example_items_uow")
def example_items_uow_fixture() -> ExampleItemUnitOfWork:
    yield ExampleItemUnitOfWorkTest()


@pytest.fixture(name="example_items")
def example_items_crud_fixture(example_items_uow: ExampleItemUnitOfWork) -> ExampleItemCrud:
    with example_items_uow as example_items:
        yield example_items


@pytest.fixture(name="example_item_create")
def example_item_create_data():
    yield ExampleItemCreate(title="test")


@pytest.fixture(name="example_item")
def get_example_item(example_items: ExampleItemCrud, example_item_create: ExampleItemCreate) -> ExampleItemBase:
    example_item = example_items.create(example_item_create)
    example_items.commit()
    yield example_item


@pytest.fixture(name="user_example_item")
def get_user_example_item(
        example_items: ExampleItemCrud,
        example_item_create: ExampleItemCreate,
        user: UserBase
) -> ExampleItemBase:
    example_item_create.owner_id = user.id
    example_item = example_items.create(example_item_create)
    example_items.commit()
    yield example_item


@pytest.fixture(name="app_dependencies")
def get_app_dependencies(example_items: ExampleItemCrud):
    def get_test_crud():
        return example_items

    return [(get_example_items_crud, get_test_crud)]
