"""Schema and service-flow integration tests for the django-bolt skeleton.

The django-bolt API runs on a Rust HTTP layer, so these tests validate the
schemas and service helpers directly without going through HTTP transport.
"""

import pytest

from django.contrib.auth.models import User

from app.models import CatalogItem, Order, OrderAddress, OrderLine, Project, Task, UserProfile
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


# --------------------------------------------------------------------------- #
#  Order workflow tests
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_order_workflow_full():
    """Full order workflow: register, login, create catalog items, create
    order, add lines, set address, submit, approve with wait_minutes+feedback."""
    # Register and login
    user = AuthService.register_user("orderer", "orderer@example.com", "pass123")
    result = AuthService.authenticate_user("orderer", "pass123")
    assert result is not None
    assert "access" in result

    # Create catalog items
    pizza = CatalogItem.objects.create(
        name="Pizza", price=12.50, category="food", description="Margherita"
    )
    soda = CatalogItem.objects.create(
        name="Soda", price=2.00, category="drink", description="Cola"
    )
    assert pizza.available is True
    assert soda.available is True

    # Create draft order
    order = Order.objects.create(user=user, status="draft")
    assert order.status == "draft"

    # Add lines — unit_price comes from catalog
    line1 = OrderLine.objects.create(
        order=order, catalog_item=pizza, quantity=2, unit_price=pizza.price
    )
    line2 = OrderLine.objects.create(
        order=order, catalog_item=soda, quantity=3, unit_price=soda.price
    )
    assert line1.unit_price == 12.50
    assert line2.quantity == 3
    assert order.lines.count() == 2

    # Set address
    address = OrderAddress.objects.create(
        order=order,
        street="123 Main St",
        city="Springfield",
        zip_code="62704",
        phone="555-1234",
        notes="Ring bell twice",
    )
    assert address.order_id == order.id

    # Submit: draft -> pending
    from django.utils import timezone
    order.status = "pending"
    order.submitted_at = timezone.now()
    order.save()
    order.refresh_from_db()
    assert order.status == "pending"
    assert order.submitted_at is not None

    # Approve: pending -> approved with wait_minutes + feedback
    order.status = "approved"
    order.wait_minutes = 30
    order.feedback = "Looks good, delivering soon"
    order.save()
    order.refresh_from_db()
    assert order.status == "approved"
    assert order.wait_minutes == 30
    assert order.feedback == "Looks good, delivering soon"


@pytest.mark.django_db
def test_order_reject():
    """Create order, submit, reject with feedback."""
    user = AuthService.register_user("rejecter", "rejecter@example.com", "pass456")

    # Create catalog item and order with a line
    item = CatalogItem.objects.create(name="Widget", price=5.00, category="misc")
    order = Order.objects.create(user=user, status="draft")
    OrderLine.objects.create(
        order=order, catalog_item=item, quantity=1, unit_price=item.price
    )

    # Submit: draft -> pending
    from django.utils import timezone
    order.status = "pending"
    order.submitted_at = timezone.now()
    order.save()
    order.refresh_from_db()
    assert order.status == "pending"

    # Reject: pending -> rejected with feedback
    order.status = "rejected"
    order.feedback = "Out of stock"
    order.save()
    order.refresh_from_db()
    assert order.status == "rejected"
    assert order.feedback == "Out of stock"
