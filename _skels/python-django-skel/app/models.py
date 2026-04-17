"""Wrapper-shared models.

Schemas mirror the django-bolt skeleton's ``app/models.py`` so a
single ``_shared/db.sqlite3`` is interchangeable across every
dev_skel backend. The User model stays Django's default
``django.contrib.auth.models.User`` — keeping it simple and
admin-friendly.
"""

from django.contrib.auth.models import User
from django.db import models


class Category(models.Model):
    """Wrapper-shared category resource."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Item(models.Model):
    """Wrapper-shared CRUD resource consumed by React via ``/api/items``."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    category = models.ForeignKey(
        "Category", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "items"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.name


class ReactState(models.Model):
    """Per-user JSON KV store backing the React ``useAppState`` hook.

    The React frontend (see
    ``ts-react-skel/src/state/state-api.ts``) stores values as opaque
    JSON strings; the backend never has to know the shape. Values
    travel as text on the wire to keep the contract universal.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="react_state",
    )
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "react_state"
        unique_together = ("user", "key")
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.user.username}:{self.key}"
