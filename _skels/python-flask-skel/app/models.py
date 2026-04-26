"""SQLAlchemy models for the wrapper-shared backend stack.

Schemas mirror the django-bolt skeleton's ``app/models.py`` so a single
``_shared/db.sqlite3`` is interchangeable across every dev_skel
backend (Python: django, django-bolt, fastapi, flask; JVM: spring;
Rust: actix, axum). The React frontend's typed fetch client + JWT
auth flow consumes the same shape regardless of which backend is
serving it.
"""

from datetime import datetime

from app import db


class User(db.Model):
    """Wrapper-shared user account.

    Backs ``/api/auth/register`` and ``/api/auth/login``. The password
    is stored as a bcrypt hash; ``email`` is captured for completeness
    (the React skel asks for it on register) but not used for auth.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Category(db.Model):
    """Wrapper-shared category resource.

    Categories are shared (not per-user) but all CRUD endpoints still
    require a JWT bearer token. The ``name`` column has a unique
    constraint matching the django-bolt / fastapi skeletons.
    """

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("Item", backref="category", lazy="select")

    def to_dict(self):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Item(db.Model):
    """Wrapper-shared CRUD resource consumed by React via ``/api/items``."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(2048), nullable=True)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_completed": bool(self.is_completed),
            "category_id": self.category_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CatalogItem(db.Model):
    """Wrapper-shared catalog entry available for ordering.

    Represents a purchasable product or service that can be referenced
    by ``OrderLine`` rows. Prices are stored as ``Numeric(10, 2)`` to
    avoid floating-point rounding issues.
    """

    __tablename__ = "catalog_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "price": str(self.price),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Order(db.Model):
    """Wrapper-shared order header tied to a user account.

    Lifecycle: draft -> submitted -> approved / rejected.
    ``wait_minutes`` and ``feedback`` are optional fields populated
    during the approval / rejection step.
    """

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = db.Column(db.String(50), nullable=False, default="draft")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    wait_minutes = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)

    lines = db.relationship("OrderLine", backref="order", lazy="select", cascade="all, delete-orphan")
    address = db.relationship("OrderAddress", backref="order", uselist=False, lazy="select", cascade="all, delete-orphan")

    def to_dict(self, include_lines=False, include_address=False):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        data = {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "wait_minutes": self.wait_minutes,
            "feedback": self.feedback,
        }
        if include_lines:
            data["lines"] = [line.to_dict() for line in self.lines]
        if include_address:
            data["address"] = self.address.to_dict() if self.address else None
        return data


class OrderLine(db.Model):
    """Single line item within an order, referencing a ``CatalogItem``."""

    __tablename__ = "order_lines"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_item_id = db.Column(
        db.Integer,
        db.ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    def to_dict(self):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        return {
            "id": self.id,
            "order_id": self.order_id,
            "catalog_item_id": self.catalog_item_id,
            "quantity": self.quantity,
            "unit_price": str(self.unit_price),
        }


class OrderAddress(db.Model):
    """Delivery address attached to a single order (one-to-one)."""

    __tablename__ = "order_addresses"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    street = db.Column(db.String(255), nullable=False, default="")
    city = db.Column(db.String(255), nullable=False, default="")
    zip_code = db.Column(db.String(20), nullable=False, default="")
    phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        return {
            "id": self.id,
            "order_id": self.order_id,
            "street": self.street,
            "city": self.city,
            "zip_code": self.zip_code,
            "phone": self.phone or "",
            "notes": self.notes or "",
        }


class ReactState(db.Model):
    """Per-user JSON KV store backing the React ``useAppState`` hook.

    The wire format the React frontend uses (see
    ``ts-react-skel/src/state/state-api.ts``) stores values as opaque
    JSON strings, so the backend never has to know the shape.
    """

    __tablename__ = "react_state"
    __table_args__ = (
        db.UniqueConstraint("user_id", "key", name="uq_react_state_user_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
