"""Pydantic request/response schemas for the wrapper-shared API.

Field names match the django-bolt skel so a single React frontend can
target both backends interchangeably (the React skel's `src/api/items.ts`
and `src/api/auth/*` clients send these exact shapes).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    email: str
    password: str = Field(min_length=1)
    password_confirm: str = Field(min_length=1)


class RegisterUser(BaseModel):
    id: int
    username: str
    email: str


class RegisterResponse(BaseModel):
    user: RegisterUser


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access: str
    refresh: str
    user_id: int
    username: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = ""


class CategoryRead(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = ""
    is_completed: Optional[bool] = False
    category_id: Optional[int] = None


class ItemRead(BaseModel):
    id: int
    name: str
    description: str
    is_completed: bool
    category_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ReactStateUpsert(BaseModel):
    value: str
