"""`/api/catalog` + `/api/orders` -- multi-entity order workflow.

Demonstrates a domain with multiple related entities, status transitions,
nested detail responses, and cross-entity operations. Follows the same
direct-SQLModel + session pattern as `items.py` and `categories.py`.

See ``order_models.py`` for the table definitions and Pydantic schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from .deps import CurrentUser, SessionDep
from .order_models import (
    AddLineBody,
    AddressBody,
    AddressRead,
    ApproveBody,
    CatalogItem,
    CatalogItemCreate,
    CatalogItemRead,
    Order,
    OrderAddress,
    OrderDetailRead,
    OrderLine,
    OrderLineRead,
    OrderRead,
    OrderStatus,
    RejectBody,
)

router = APIRouter(tags=["wrapper-orders"])

# --------------------------------------------------------------------------- #
#  Catalog endpoints
# --------------------------------------------------------------------------- #


@router.get("/api/catalog", response_model=List[CatalogItemRead])
def list_catalog(session: SessionDep):
    items = session.exec(select(CatalogItem)).all()
    return [CatalogItemRead(**i.model_dump()) for i in items]


@router.get("/api/catalog/{item_id}", response_model=CatalogItemRead)
def get_catalog_item(item_id: int, session: SessionDep):
    item = session.get(CatalogItem, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catalog item not found")
    return CatalogItemRead(**item.model_dump())


@router.post("/api/catalog", response_model=CatalogItemRead, status_code=201)
def create_catalog_item(
    body: CatalogItemCreate, _user: CurrentUser, session: SessionDep,
):
    item = CatalogItem(**body.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return CatalogItemRead(**item.model_dump())


# --------------------------------------------------------------------------- #
#  Order CRUD
# --------------------------------------------------------------------------- #


@router.post("/api/orders", response_model=OrderRead, status_code=201)
def create_order(user: CurrentUser, session: SessionDep):
    order = Order(user_id=user.id)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.get("/api/orders", response_model=List[OrderRead])
def list_orders(user: CurrentUser, session: SessionDep):
    return session.exec(
        select(Order).where(Order.user_id == user.id)
    ).all()


@router.get("/api/orders/{order_id}", response_model=OrderDetailRead)
def get_order(order_id: int, user: CurrentUser, session: SessionDep):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your order")
    lines = session.exec(
        select(OrderLine).where(OrderLine.order_id == order_id)
    ).all()
    address = session.exec(
        select(OrderAddress).where(OrderAddress.order_id == order_id)
    ).first()
    return OrderDetailRead(
        **order.model_dump(),
        lines=[OrderLineRead(**ln.model_dump()) for ln in lines],
        address=AddressRead(**address.model_dump()) if address else None,
    )


# --------------------------------------------------------------------------- #
#  Order lines
# --------------------------------------------------------------------------- #


@router.post("/api/orders/{order_id}/lines", status_code=201)
def add_line(
    order_id: int, body: AddLineBody, user: CurrentUser, session: SessionDep,
):
    order = _get_draft(order_id, user, session)
    cat = session.get(CatalogItem, body.catalog_item_id)
    if not cat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catalog item not found")
    line = OrderLine(
        order_id=order_id,
        catalog_item_id=body.catalog_item_id,
        quantity=body.quantity,
        unit_price=cat.price,
    )
    session.add(line)
    session.commit()
    session.refresh(line)
    return OrderLineRead(**line.model_dump())


@router.delete("/api/orders/{order_id}/lines/{line_id}")
def remove_line(
    order_id: int, line_id: int, user: CurrentUser, session: SessionDep,
):
    _get_draft(order_id, user, session)
    line = session.get(OrderLine, line_id)
    if not line or line.order_id != order_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Line not found")
    session.delete(line)
    session.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Order address
# --------------------------------------------------------------------------- #


@router.put("/api/orders/{order_id}/address")
def set_address(
    order_id: int, body: AddressBody, user: CurrentUser, session: SessionDep,
):
    _get_draft(order_id, user, session)
    existing = session.exec(
        select(OrderAddress).where(OrderAddress.order_id == order_id)
    ).first()
    if existing:
        for k, v in body.model_dump().items():
            setattr(existing, k, v)
        session.add(existing)
    else:
        session.add(OrderAddress(order_id=order_id, **body.model_dump()))
    session.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Status transitions
# --------------------------------------------------------------------------- #


@router.post("/api/orders/{order_id}/submit", response_model=OrderRead)
def submit_order(order_id: int, user: CurrentUser, session: SessionDep):
    order = _get_draft(order_id, user, session)
    order.status = OrderStatus.pending.value
    order.submitted_at = datetime.utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.post("/api/orders/{order_id}/approve", response_model=OrderRead)
def approve_order(
    order_id: int, body: ApproveBody, user: CurrentUser, session: SessionDep,
):
    order = _get_pending(order_id, session)
    order.status = OrderStatus.approved.value
    order.wait_minutes = body.wait_minutes
    order.feedback = body.feedback
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.post("/api/orders/{order_id}/reject", response_model=OrderRead)
def reject_order(
    order_id: int, body: RejectBody, user: CurrentUser, session: SessionDep,
):
    order = _get_pending(order_id, session)
    order.status = OrderStatus.rejected.value
    order.feedback = body.feedback
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def _get_draft(order_id: int, user: CurrentUser, session: SessionDep) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your order")
    if order.status != OrderStatus.draft.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Order must be in draft status"
        )
    return order


def _get_pending(order_id: int, session: SessionDep) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.status != OrderStatus.pending.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Order must be in pending status"
        )
    return order
