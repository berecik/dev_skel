from typing import Annotated
from fastapi import Depends

from .models import ExampleItemUnitOfWork
from .adapters.sql import get_example_item_uow, ExampleItemCrud

ExampleItemsUowDep = Annotated[ExampleItemUnitOfWork, Depends(get_example_item_uow)]


def get_example_items_crud(example_items_uow: ExampleItemsUowDep) -> ExampleItemCrud:
    with example_items_uow as example_items:
        yield example_items


ExampleItemsDep = Annotated[ExampleItemCrud, Depends(get_example_items_crud)]
