"""SQLModel tables + a tiny session helper for the wrapper-shared API.

The wrapper-shared layer ships its own minimal user table (`wrapper_user`)
because the existing `core.users.db.User` model is built around an
``EmailStr`` primary lookup, while the React frontend's register/login
calls send an opaque `username` field. Keeping the table separate lets
the wrapper-shared API stay schema-compatible with the django-bolt
skel without rewriting the `core.users` machinery.

The `Category` table stores shared categories that items can optionally
belong to. Categories are not per-user — any authenticated user may
create/edit/delete them. The `name` column has a unique constraint.

The `Item` table uses ``__tablename__ = "items"`` (matching the
django-bolt skel's `Item` model) so the same wrapper-shared SQLite file
remains usable across stacks. The columns mirror the django-bolt schema
verbatim — `name`, `description`, `is_completed`, `created_at`,
`updated_at` — see `_docs/SHARED-DATABASE-CONVENTIONS.md`. Items carry
an optional ``category_id`` FK to the ``categories`` table (ON DELETE
SET NULL).

The `react_state` table backs the `/api/state` endpoints the React
state-management layer calls. Per-user JSON key/value entries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, Session, SQLModel

import config


class WrapperUser(SQLModel, table=True):
    """User table for the wrapper-shared register/login flow."""

    __tablename__ = "wrapper_user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Category(SQLModel, table=True):
    """Shared categories table — not per-user."""

    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, sa_column_kwargs={"unique": True})
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Item(SQLModel, table=True):
    """Wrapper-shared `items` table — shape mirrors django-bolt's `Item`."""

    __tablename__ = "items"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: str = Field(default="")
    is_completed: bool = Field(default=False)
    category_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReactState(SQLModel, table=True):
    """Per-user JSON key/value store for the React state-management layer."""

    __tablename__ = "react_state"
    __table_args__ = (UniqueConstraint("user_id", "key", name="_user_key_uc"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="wrapper_user.id")
    key: str = Field(index=True)
    value: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# A standalone engine for the wrapper-shared layer. Importing this
# module is enough to register the three tables above with the shared
# `SQLModel.metadata`, so the rest of the app's `engine_factory` calls
# will pick them up automatically. We also create the tables eagerly
# here so the first HTTP request does not race with the schema being
# materialised on disk.
def _enable_sqlite_fks(dbapi_connection, _connection_record):
    """Enable SQLite foreign key enforcement (required for ON DELETE SET NULL)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


_engine = create_engine(
    config.SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False}
    if config.SQLALCHEMY_DATABASE_URI.startswith("sqlite")
    else {},
)
if config.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
    from sqlalchemy import event
    event.listen(_engine, "connect", _enable_sqlite_fks)
SQLModel.metadata.create_all(_engine, tables=[
    WrapperUser.__table__,
    Category.__table__,
    Item.__table__,
    ReactState.__table__,
])
_SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a wrapper-shared SQLModel session."""

    session = Session(_engine, autoflush=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
