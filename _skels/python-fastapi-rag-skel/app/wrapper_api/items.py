"""`/api/items` CRUD for the wrapper-shared items table.

Mirrors the django-bolt skel's `ItemViewSet` so the React skel's
`src/api/items.ts` client works against either backend without any
code changes. All endpoints require a JWT bearer token issued by the
wrapper-shared `/api/auth/login` flow.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from .db import Item
from .deps import CurrentUser, SessionDep
from .schemas import ItemCreate, ItemRead

router = APIRouter(prefix="/api/items", tags=["wrapper-items"])


def _to_read(item: Item) -> ItemRead:
    return ItemRead(
        id=item.id,
        name=item.name,
        description=item.description or "",
        is_completed=bool(item.is_completed),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=List[ItemRead])
def list_items(
    session: SessionDep,
    _user: CurrentUser,
) -> List[ItemRead]:
    items = session.exec(select(Item).order_by(Item.id)).all()
    return [_to_read(i) for i in items]


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    payload: ItemCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> ItemRead:
    item = Item(
        name=payload.name,
        description=payload.description or "",
        is_completed=bool(payload.is_completed),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return _to_read(item)


@router.get("/{item_id}", response_model=ItemRead)
def retrieve_item(
    item_id: int,
    session: SessionDep,
    _user: CurrentUser,
) -> ItemRead:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _to_read(item)


@router.post("/{item_id}/complete", response_model=ItemRead)
def complete_item(
    item_id: int,
    session: SessionDep,
    _user: CurrentUser,
) -> ItemRead:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.is_completed = True
    item.updated_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return _to_read(item)
