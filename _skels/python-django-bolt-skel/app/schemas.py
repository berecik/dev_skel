"""msgspec.Struct schemas for the django-bolt skeleton service.

Using msgspec instead of DRF serializers gives ~5-10x faster (de)serialisation
and pairs naturally with django-bolt's Rust HTTP layer.
"""

import msgspec

from app.models import (
    CatalogItem,
    Category,
    Item,
    Order,
    OrderAddress,
    OrderLine,
    Project,
    ReactState,
    Task,
    UserProfile,
)


class UserSchema(msgspec.Struct):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str

    @classmethod
    def from_model(cls, obj) -> "UserSchema":
        return cls(
            id=obj.id,
            username=obj.username,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
        )


class UserProfileSchema(msgspec.Struct):
    id: int
    user: UserSchema
    bio: str
    avatar_url: str

    @classmethod
    def from_model(cls, obj) -> "UserProfileSchema":
        return cls(
            id=obj.id,
            user=UserSchema.from_model(obj.user),
            bio=obj.bio,
            avatar_url=str(obj.avatar_url),
        )


class RegisterSchema(msgspec.Struct):
    username: str
    email: str
    password: str
    password_confirm: str


class LoginSchema(msgspec.Struct):
    username: str
    password: str


class OAuthLoginSchema(msgspec.Struct):
    provider: str
    access_token: str


class RefreshSchema(msgspec.Struct):
    refresh: str


class ProjectSchema(msgspec.Struct):
    id: int
    name: str
    description: str
    owner: UserSchema
    task_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, obj) -> "ProjectSchema":
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            owner=UserSchema.from_model(obj.owner),
            task_count=obj.tasks.count(),
            created_at=str(obj.created_at),
            updated_at=str(obj.updated_at),
        )


class ProjectCreateSchema(msgspec.Struct):
    name: str
    description: str = ""


class TaskSchema(msgspec.Struct):
    id: int
    title: str
    description: str
    project_id: int
    assignee_id: int | None
    priority: str
    status: str
    is_completed: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, obj) -> "TaskSchema":
        return cls(
            id=obj.id,
            title=obj.title,
            description=obj.description,
            project_id=obj.project_id,
            assignee_id=obj.assignee_id,
            priority=obj.priority,
            status=obj.status,
            is_completed=obj.is_completed,
            created_at=str(obj.created_at),
            updated_at=str(obj.updated_at),
        )


class TaskDetailSchema(msgspec.Struct):
    id: int
    title: str
    description: str
    project_id: int
    assignee_id: int | None
    priority: str
    status: str
    is_completed: bool
    created_at: str
    updated_at: str
    project: ProjectSchema
    assignee: UserSchema | None

    @classmethod
    def from_model(cls, obj) -> "TaskDetailSchema":
        return cls(
            id=obj.id,
            title=obj.title,
            description=obj.description,
            project_id=obj.project_id,
            assignee_id=obj.assignee_id,
            priority=obj.priority,
            status=obj.status,
            is_completed=obj.is_completed,
            created_at=str(obj.created_at),
            updated_at=str(obj.updated_at),
            project=ProjectSchema.from_model(obj.project),
            assignee=UserSchema.from_model(obj.assignee) if obj.assignee else None,
        )


class TaskCreateSchema(msgspec.Struct, kw_only=True):
    title: str
    project: int
    description: str = ""
    assignee: int | None = None
    priority: str = "medium"
    status: str = "todo"


# --------------------------------------------------------------------------- #
#  Wrapper-shared `categories` resource.
# --------------------------------------------------------------------------- #


class CategorySchema(msgspec.Struct):
    id: int
    name: str
    description: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, obj) -> "CategorySchema":
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            created_at=str(obj.created_at),
            updated_at=str(obj.updated_at),
        )


class CategoryCreateSchema(msgspec.Struct):
    name: str
    description: str | None = None


# --------------------------------------------------------------------------- #
#  Wrapper-shared `items` resource (consumed by the React skeleton).
# --------------------------------------------------------------------------- #


class ItemSchema(msgspec.Struct):
    """Shape of a row in the wrapper-shared `items` table.

    Mirrors the canonical schema documented in
    `_docs/SHARED-DATABASE-CONVENTIONS.md` so the React frontend, the
    `_bin/skel-test-shared-db` integration runner, and every other backend
    speak the same payload.
    """

    id: int
    name: str
    description: str | None
    is_completed: bool
    category_id: int | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, obj) -> "ItemSchema":
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            is_completed=obj.is_completed,
            category_id=obj.category_id,
            created_at=str(obj.created_at),
            updated_at=str(obj.updated_at),
        )


class ItemCreateSchema(msgspec.Struct):
    """Body shape for `POST /api/items`."""

    name: str
    description: str | None = None
    is_completed: bool = False
    category_id: int | None = None


# --------------------------------------------------------------------------- #
#  React state save/load
# --------------------------------------------------------------------------- #


class ReactStateUpsertSchema(msgspec.Struct):
    """Body shape for `PUT /api/state/<key>`.

    `value` is an arbitrary JSON payload — the React layer is the
    only consumer that knows the shape. The backend stores it in a
    ``JSONField`` so round-trips preserve types (dicts, lists, etc.).
    """

    value: object  # any JSON-serializable value


# --------------------------------------------------------------------------- #
#  Catalog / Order workflow
# --------------------------------------------------------------------------- #


class CatalogItemSchema(msgspec.Struct):
    id: int
    name: str
    description: str
    price: float
    category: str
    available: bool

    @classmethod
    def from_model(cls, obj) -> "CatalogItemSchema":
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            price=obj.price,
            category=obj.category,
            available=obj.available,
        )


class CatalogItemCreateSchema(msgspec.Struct, kw_only=True):
    name: str
    price: float
    category: str = ""
    description: str = ""
    available: bool = True


class OrderLineSchema(msgspec.Struct):
    id: int
    catalog_item_id: int
    catalog_item_name: str
    quantity: int
    unit_price: float

    @classmethod
    def from_model(cls, obj) -> "OrderLineSchema":
        return cls(
            id=obj.id,
            catalog_item_id=obj.catalog_item_id,
            catalog_item_name=obj.catalog_item.name if obj.catalog_item else "",
            quantity=obj.quantity,
            unit_price=obj.unit_price,
        )


class OrderAddressSchema(msgspec.Struct):
    street: str
    city: str
    zip_code: str
    phone: str
    notes: str

    @classmethod
    def from_model(cls, obj) -> "OrderAddressSchema":
        return cls(
            street=obj.street,
            city=obj.city,
            zip_code=obj.zip_code,
            phone=obj.phone,
            notes=obj.notes,
        )


class OrderSchema(msgspec.Struct):
    id: int
    user_id: int
    status: str
    created_at: str
    submitted_at: str | None
    wait_minutes: int | None
    feedback: str | None

    @classmethod
    def from_model(cls, obj) -> "OrderSchema":
        return cls(
            id=obj.id,
            user_id=obj.user_id,
            status=obj.status,
            created_at=str(obj.created_at),
            submitted_at=str(obj.submitted_at) if obj.submitted_at else None,
            wait_minutes=obj.wait_minutes,
            feedback=obj.feedback,
        )


class OrderDetailSchema(msgspec.Struct):
    id: int
    user_id: int
    status: str
    created_at: str
    submitted_at: str | None
    wait_minutes: int | None
    feedback: str | None
    lines: list[OrderLineSchema]
    address: OrderAddressSchema | None

    @classmethod
    def from_model(cls, obj, lines=None, address=None) -> "OrderDetailSchema":
        return cls(
            id=obj.id,
            user_id=obj.user_id,
            status=obj.status,
            created_at=str(obj.created_at),
            submitted_at=str(obj.submitted_at) if obj.submitted_at else None,
            wait_minutes=obj.wait_minutes,
            feedback=obj.feedback,
            lines=[OrderLineSchema.from_model(l) for l in (lines or [])],
            address=OrderAddressSchema.from_model(address) if address else None,
        )


class OrderLineCreateSchema(msgspec.Struct):
    catalog_item_id: int
    quantity: int = 1


class OrderAddressUpsertSchema(msgspec.Struct, kw_only=True):
    street: str
    city: str
    zip_code: str
    phone: str = ""
    notes: str = ""


class OrderApproveSchema(msgspec.Struct, kw_only=True):
    wait_minutes: int | None = None
    feedback: str | None = None


class OrderRejectSchema(msgspec.Struct, kw_only=True):
    feedback: str | None = None
