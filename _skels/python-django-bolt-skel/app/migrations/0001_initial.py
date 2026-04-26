"""Initial migration — all models for the django-bolt skeleton.

Auto-generated equivalent (hand-written because Django is not installed
in the skeleton dev environment).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ----------------------------------------------------------
        # UserProfile
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bio", models.TextField(blank=True, default="")),
                ("avatar_url", models.URLField(blank=True, default="", max_length=2048)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        # ----------------------------------------------------------
        # Project
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="projects", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ----------------------------------------------------------
        # Task
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="Task",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("priority", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="medium", max_length=10)),
                ("status", models.CharField(choices=[("todo", "To Do"), ("in_progress", "In Progress"), ("in_review", "In Review"), ("done", "Done")], default="todo", max_length=20)),
                ("is_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="app.project")),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_tasks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ----------------------------------------------------------
        # Category
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "categories", "ordering": ["name"]},
        ),
        # ----------------------------------------------------------
        # Item
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                ("is_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="items", to="app.category")),
            ],
            options={"db_table": "items", "ordering": ["-created_at"]},
        ),
        # ----------------------------------------------------------
        # ReactState
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="ReactState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=255)),
                ("value", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="react_state", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "react_state", "ordering": ["key"], "unique_together": {("user", "key")}},
        ),
        # ----------------------------------------------------------
        # CatalogItem
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="CatalogItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("price", models.FloatField()),
                ("category", models.CharField(blank=True, default="", max_length=100)),
                ("available", models.BooleanField(default=True)),
            ],
            options={"db_table": "catalog_items"},
        ),
        # ----------------------------------------------------------
        # Order
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("draft", "draft"), ("pending", "pending"), ("approved", "approved"), ("rejected", "rejected")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("wait_minutes", models.IntegerField(blank=True, null=True)),
                ("feedback", models.TextField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "orders"},
        ),
        # ----------------------------------------------------------
        # OrderLine
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="OrderLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.IntegerField(default=1)),
                ("unit_price", models.FloatField(default=0.0)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="app.order")),
                ("catalog_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.catalogitem")),
            ],
            options={"db_table": "order_lines"},
        ),
        # ----------------------------------------------------------
        # OrderAddress
        # ----------------------------------------------------------
        migrations.CreateModel(
            name="OrderAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("street", models.CharField(max_length=255)),
                ("city", models.CharField(max_length=100)),
                ("zip_code", models.CharField(max_length=20)),
                ("phone", models.CharField(blank=True, default="", max_length=50)),
                ("notes", models.TextField(blank=True, default="")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="address", to="app.order")),
            ],
            options={"db_table": "order_addresses"},
        ),
    ]
