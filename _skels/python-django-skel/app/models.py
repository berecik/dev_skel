"""Wrapper-shared models.

Schemas mirror the django-bolt skeleton's ``app/models.py`` so a
single ``_shared/db.sqlite3`` is interchangeable across every
dev_skel backend. The User model stays Django's default
``django.contrib.auth.models.User`` — keeping it simple and
admin-friendly.
"""

from django.contrib.auth.models import User
from django.db import models


# --------------------------------------------------------------------------- #
#  Order workflow models
# --------------------------------------------------------------------------- #


class CatalogItem(models.Model):
    """Product available for ordering."""

    name = models.CharField(max_length=255)
    description = models.TextField(default="", blank=True)
    price = models.FloatField()
    category = models.CharField(max_length=100, default="", blank=True)
    available = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_items"

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    """User order with draft/pending/approved/rejected lifecycle."""

    STATUS_CHOICES = [
        ("draft", "draft"),
        ("pending", "pending"),
        ("approved", "approved"),
        ("rejected", "rejected"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    wait_minutes = models.IntegerField(null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "orders"

    def __str__(self) -> str:
        return f"Order({self.id}, {self.status})"


class OrderLine(models.Model):
    """Line item within an order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    unit_price = models.FloatField(default=0.0)

    class Meta:
        db_table = "order_lines"

    def __str__(self) -> str:
        return f"OrderLine({self.id}, qty={self.quantity})"


class OrderAddress(models.Model):
    """Shipping/delivery address attached to an order."""

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="address")
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=50, default="", blank=True)
    notes = models.TextField(default="", blank=True)

    class Meta:
        db_table = "order_addresses"

    def __str__(self) -> str:
        return f"OrderAddress({self.order_id})"


# --------------------------------------------------------------------------- #
#  Wrapper-shared models
# --------------------------------------------------------------------------- #


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
