"""SQLModel tables + Pydantic schemas for the order workflow.

Demonstrates a multi-entity domain with status transitions, nested
responses, and cross-entity operations. Generic enough to serve as a
blueprint for any order-like workflow (e-commerce, restaurant, service
requests, etc.).

Tables: ``catalog_items``, ``orders``, ``order_lines``, ``order_addresses``.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    pass  # forward refs resolved by SQLModel at runtime


# --------------------------------------------------------------------------- #
#  Enums
# --------------------------------------------------------------------------- #


class OrderStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# --------------------------------------------------------------------------- #
#  SQLModel tables
# --------------------------------------------------------------------------- #


class CatalogItem(SQLModel, table=True):
    """What can be ordered."""

    __tablename__ = "catalog_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    price: float
    category: str = ""
    available: bool = True


class Order(SQLModel, table=True):
    """A user's order with a draft → pending → approved|rejected lifecycle."""

    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="wrapper_user.id")
    status: str = Field(default=OrderStatus.draft.value)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    wait_minutes: Optional[int] = None
    feedback: Optional[str] = None

    lines: List["OrderLine"] = Relationship(back_populates="order")
    address: Optional["OrderAddress"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"uselist": False},
    )


class OrderLine(SQLModel, table=True):
    """A line item linking an order to a catalog item."""

    __tablename__ = "order_lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id")
    catalog_item_id: int = Field(foreign_key="catalog_items.id")
    quantity: int = 1
    unit_price: float = 0.0

    order: Optional[Order] = Relationship(back_populates="lines")


class OrderAddress(SQLModel, table=True):
    """Delivery/shipping address attached to an order (one-to-one)."""

    __tablename__ = "order_addresses"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", unique=True)
    street: str
    city: str
    zip_code: str
    phone: str = ""
    notes: str = ""

    order: Optional[Order] = Relationship(back_populates="address")


# --------------------------------------------------------------------------- #
#  Pydantic request/response schemas
# --------------------------------------------------------------------------- #


class CatalogItemCreate(BaseModel):
    name: str
    price: float
    category: str = ""
    description: str = ""
    available: bool = True


class CatalogItemRead(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: str
    available: bool


class AddLineBody(BaseModel):
    catalog_item_id: int
    quantity: int = 1


class AddressBody(BaseModel):
    street: str
    city: str
    zip_code: str
    phone: str = ""
    notes: str = ""


class ApproveBody(BaseModel):
    wait_minutes: int
    feedback: str


class RejectBody(BaseModel):
    feedback: str


class OrderLineRead(BaseModel):
    id: int
    catalog_item_id: int
    quantity: int
    unit_price: float


class AddressRead(BaseModel):
    id: int
    street: str
    city: str
    zip_code: str
    phone: str
    notes: str


class OrderRead(BaseModel):
    id: int
    user_id: int
    status: str
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    wait_minutes: Optional[int] = None
    feedback: Optional[str] = None


class OrderDetailRead(OrderRead):
    lines: List[OrderLineRead] = []
    address: Optional[AddressRead] = None
