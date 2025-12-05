from app.example_items.models import ExampleItemCreate, ExampleItemUnitOfWork, ExampleItemCrud, ExampleItemBase
from app.example_items.adapters.sql import get_example_item_uow


def test_create_example_item(example_items_uow: ExampleItemUnitOfWork, example_item_create: ExampleItemCreate):
    with example_items_uow as example_items:
        example_item = example_items.create(example_item_create)
        example_items.commit()
        assert example_item.id == 1
        assert example_item.title == example_item_create.title
        assert example_item.description == example_item_create.description
        assert example_item.owner_id == example_item_create.owner_id
        assert len(example_items) == 1


def test_get_example_item(example_items: ExampleItemCrud, example_item: ExampleItemBase):
    current_example_item = example_items.get(example_item.id)
    assert current_example_item.id == example_item.id
    assert current_example_item.title == example_item.title
    assert current_example_item.description == example_item.description
    assert current_example_item.owner_id == example_item.owner_id


def test_update_example_item(example_items: ExampleItemCrud, example_item: ExampleItemBase):
    example_item.title = "new title"
    example_items.update(obj_in=example_item, id=example_item.id)
    example_items.commit()

    current_example_item = example_items.get(example_item.id)

    assert current_example_item.id == example_item.id
    assert current_example_item.title == "new title"
    assert current_example_item.description == example_item.description
    assert current_example_item.owner_id == example_item.owner_id


def test_delete_example_item(example_items: ExampleItemCrud, example_item: ExampleItemBase):
    removed = example_items.remove(id=example_item.id)
    assert removed is True
    assert len(example_items) == 0
