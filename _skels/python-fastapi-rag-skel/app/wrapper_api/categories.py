"""`/api/categories` CRUD for the wrapper-shared categories table.

Categories are shared (not per-user) but all endpoints still require a
JWT bearer token so unauthenticated callers cannot modify them.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from .db import Category
from .deps import CurrentUser, SessionDep
from .schemas import CategoryCreate, CategoryRead

router = APIRouter(prefix="/api/categories", tags=["wrapper-categories"])


def _to_read(cat: Category) -> CategoryRead:
    return CategoryRead(
        id=cat.id,
        name=cat.name,
        description=cat.description or "",
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


@router.get("", response_model=List[CategoryRead])
def list_categories(
    session: SessionDep,
    _user: CurrentUser,
) -> List[CategoryRead]:
    cats = session.exec(select(Category).order_by(Category.id)).all()
    return [_to_read(c) for c in cats]


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CategoryCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> CategoryRead:
    cat = Category(
        name=payload.name,
        description=payload.description or "",
    )
    session.add(cat)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{payload.name}' already exists",
        )
    session.refresh(cat)
    return _to_read(cat)


@router.get("/{category_id}", response_model=CategoryRead)
def retrieve_category(
    category_id: int,
    session: SessionDep,
    _user: CurrentUser,
) -> CategoryRead:
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return _to_read(cat)


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryCreate,
    session: SessionDep,
    _user: CurrentUser,
) -> CategoryRead:
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = payload.name
    cat.description = payload.description or ""
    cat.updated_at = datetime.utcnow()
    session.add(cat)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{payload.name}' already exists",
        )
    session.refresh(cat)
    return _to_read(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    session: SessionDep,
    _user: CurrentUser,
) -> Response:
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    session.delete(cat)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
