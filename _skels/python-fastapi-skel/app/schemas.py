"""Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class ItemBase(BaseModel):
    """Base item schema."""

    name: str
    description: str | None = None


class ItemCreate(ItemBase):
    """Schema for creating items."""

    pass


class ItemResponse(ItemBase):
    """Schema for item responses."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
