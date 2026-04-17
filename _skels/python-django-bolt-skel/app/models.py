"""Domain models for the django-bolt skeleton service.

Adapted from the canonical claude_on_django sandbox so the skeleton ships
with a working `User → Project → Task` graph plus an automatic UserProfile
created on user signup.
"""

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, default="")
    avatar_url = models.URLField(max_length=2048, blank=True, default="")

    def __str__(self) -> str:
        return f"Profile({self.user.username})"


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(User, related_name="projects", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        IN_REVIEW = "in_review", "In Review"
        DONE = "done", "Done"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    project = models.ForeignKey(Project, related_name="tasks", on_delete=models.CASCADE)
    assignee = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs) -> None:
    if created:
        UserProfile.objects.create(user=instance)


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
    """Wrapper-shared `items` resource.

    This model maps to the canonical `items` table that every dev_skel
    backend can serve (see ``_docs/SHARED-DATABASE-CONVENTIONS.md`` and
    ``_bin/skel-test-shared-db``). It is intentionally NOT scoped to a user
    so the integration test can pre-seed rows via raw SQL and every
    backend in the wrapper sees the same data.

    The frontend (React skeleton) calls ``GET /api/items`` against this
    table by default — see ``app/api.py`` for the BoltAPI viewset.
    """

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
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class ReactState(models.Model):
    """Per-user key/value store used by the React state-management layer.

    The React skeleton (``src/state/state-api.ts``) calls
    ``GET /api/state`` to load every slice for the current user, and
    ``PUT /api/state/<key>`` to upsert a single slice. The combination
    lets the frontend persist filter / sort / preference state across
    sessions without each component needing its own backend route.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="react_state",
    )
    key = models.CharField(max_length=255)
    value = models.JSONField(default=dict)  # arbitrary JSON payload
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "react_state"
        unique_together = ("user", "key")
        ordering = ["key"]

    def __str__(self) -> str:
        return f"ReactState({self.user_id}, {self.key})"
