"""Schema and service-flow integration tests for the django-bolt skeleton.

The django-bolt API runs on a Rust HTTP layer, so these tests validate the
schemas and service helpers directly without going through HTTP transport.
"""

import pytest

from django.contrib.auth.models import User

from app.models import Project, Task, UserProfile
from app.schemas import (
    ProjectSchema,
    RegisterSchema,
    TaskDetailSchema,
    TaskSchema,
    UserProfileSchema,
    UserSchema,
)
from app.services.auth_service import AuthService


# --------------------------------------------------------------------------- #
#  Schema round-trips
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_user_schema_from_model():
    user = User.objects.create_user(
        username="alice", email="alice@example.com", first_name="A", last_name="B"
    )
    schema = UserSchema.from_model(user)
    assert schema.id == user.id
    assert schema.username == "alice"
    assert schema.email == "alice@example.com"


@pytest.mark.django_db
def test_user_profile_schema_from_model():
    user = User.objects.create_user(username="bob", password="x")
    profile = UserProfile.objects.get(user=user)
    profile.bio = "hi"
    profile.save()
    schema = UserProfileSchema.from_model(profile)
    assert schema.user.id == user.id
    assert schema.bio == "hi"


@pytest.mark.django_db
def test_project_schema_task_count():
    user = User.objects.create_user(username="carol", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    Task.objects.create(project=project, title="t1")
    Task.objects.create(project=project, title="t2")
    Task.objects.create(project=project, title="t3")
    schema = ProjectSchema.from_model(project)
    assert schema.task_count == 3
    assert schema.owner.id == user.id


@pytest.mark.django_db
def test_task_schema_from_model():
    user = User.objects.create_user(username="dave", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    task = Task.objects.create(project=project, title="Ship it")
    schema = TaskSchema.from_model(task)
    assert schema.title == "Ship it"
    assert schema.project_id == project.id
    assert schema.priority == "medium"
    assert schema.status == "todo"


@pytest.mark.django_db
def test_task_detail_schema_with_assignee():
    user = User.objects.create_user(username="erin", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    task = Task.objects.create(project=project, title="With assignee", assignee=user)
    schema = TaskDetailSchema.from_model(task)
    assert schema.assignee is not None
    assert schema.assignee.id == user.id
    assert schema.project.id == project.id


@pytest.mark.django_db
def test_register_schema_construction():
    payload = RegisterSchema(
        username="frank", email="f@x.io", password="p", password_confirm="p"
    )
    assert payload.username == "frank"


# --------------------------------------------------------------------------- #
#  Service-level flows
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_register_then_login_flow():
    AuthService.register_user("george", "g@x.io", "secret123")
    result = AuthService.authenticate_user("george", "secret123")
    assert result is not None
    assert "access" in result


@pytest.mark.django_db
def test_owner_isolation_for_tasks():
    alice = User.objects.create_user(username="alice", password="x")
    bob = User.objects.create_user(username="bob", password="x")
    p_alice = Project.objects.create(name="Alice", owner=alice)
    p_bob = Project.objects.create(name="Bob", owner=bob)
    Task.objects.create(project=p_alice, title="alice-task")
    Task.objects.create(project=p_bob, title="bob-task")
    alice_tasks = Task.objects.filter(project__owner=alice)
    assert alice_tasks.count() == 1
    assert alice_tasks.first().title == "alice-task"


@pytest.mark.django_db
def test_task_completion_flow():
    user = User.objects.create_user(username="harry", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    task = Task.objects.create(project=project, title="Done soon")
    task.is_completed = True
    task.status = "done"
    task.save()
    refreshed = Task.objects.get(pk=task.pk)
    assert refreshed.is_completed is True
    assert refreshed.status == "done"


@pytest.mark.django_db
def test_task_cascade_on_project_delete():
    user = User.objects.create_user(username="ivan", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    Task.objects.create(project=project, title="t1")
    pid = project.id
    project.delete()
    assert Task.objects.filter(project_id=pid).count() == 0


# --------------------------------------------------------------------------- #
#  Seed & email-login tests
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_default_user_can_login():
    from app.seed import seed_default_accounts
    seed_default_accounts()
    result = AuthService.authenticate_user("user", "secret")
    assert result is not None
    assert "access" in result


@pytest.mark.django_db
def test_default_superuser_can_login():
    from app.seed import seed_default_accounts
    seed_default_accounts()
    result = AuthService.authenticate_user("admin", "secret")
    assert result is not None
    assert "access" in result


@pytest.mark.django_db
def test_login_by_email():
    from app.seed import seed_default_accounts
    seed_default_accounts()
    result = AuthService.authenticate_user("user@example.com", "secret")
    assert result is not None
    assert "access" in result


@pytest.mark.django_db
def test_login_by_email_superuser():
    from app.seed import seed_default_accounts
    seed_default_accounts()
    result = AuthService.authenticate_user("admin@example.com", "secret")
    assert result is not None
    assert "access" in result
