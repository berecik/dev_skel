from typing import Any

from fastapi import APIRouter, HTTPException

from .depts import ExampleItemsDep
from core.deps import CurrentUser
from .models import ExampleItemBase, ExampleItemCreate, ExampleItemUpdate

router = APIRouter()


@router.get("/", response_model=list[ExampleItemBase])
def read_example_items(
    example_items: ExampleItemsDep, current_user: CurrentUser
) -> Any:
    """
    Retrieve example_items.
    """

    if current_user.is_superuser:
        return example_items.list()
    else:
        return example_items.get_by_owner(owner_id=current_user.id)


@router.get("/{id}", response_model=ExampleItemBase)
def read_example_item(example_items: ExampleItemsDep, current_user: CurrentUser, id: int) -> Any:
    """
    Get example_item by ID.
    """

    example_item = example_items.get(id)
    if not example_item:
        raise HTTPException(status_code=404, detail="ExampleItem not found")
    if not current_user.is_superuser and (example_item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return example_item


@router.post("/", response_model=ExampleItemBase)
def create_example_item(
    *, example_items: ExampleItemsDep, current_user: CurrentUser, example_item_in: ExampleItemCreate
) -> Any:
    """
    Create new example_item.
    """
    if not current_user.is_superuser:
        example_item_in.owner_id = current_user.id
    example_item = example_items.create(example_item_in)
    return example_item


@router.put("/{id}", response_model=ExampleItemBase)
def update_example_item(
    *, example_items: ExampleItemsDep, current_user: CurrentUser, id: int, example_item_in: ExampleItemUpdate
) -> Any:
    """
    Update an example_item.
    """

    example_item = example_items.get(id)
    if not example_item:
        raise HTTPException(status_code=404, detail="ExampleItem not found")
    if not current_user.is_superuser and (example_item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    example_item = example_items.update(obj_in=example_item_in, id=example_item.id)

    return example_item


@router.delete("/{id}", response_model=ExampleItemBase)
def delete_example_item(example_items: ExampleItemsDep, current_user: CurrentUser, id: int) -> Any:
    """
    Delete an example_item.
    """

    example_item = example_items.get(id)
    if not example_item:
        raise HTTPException(status_code=404, detail="ExampleItem not found")
    if not current_user.is_superuser and (example_item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    example_items.remove(example_item.id)
    return example_item
