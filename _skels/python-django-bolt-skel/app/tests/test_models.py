"""Unit tests for the django-bolt skeleton models and AuthService."""

import pytest

from django.contrib.auth.models import User

from app.models import Project, Task, UserProfile
from app.services.auth_service import AuthService


# --------------------------------------------------------------------------- #
#  Models
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_user_profile_auto_created_on_user():
    user = User.objects.create_user(username="alice", email="a@x.io", password="x")
    profile = UserProfile.objects.get(user=user)
    assert str(profile) == "Profile(alice)"
    assert profile.bio == ""
    assert profile.avatar_url == ""


@pytest.mark.django_db
def test_project_create_and_str():
    user = User.objects.create_user(username="bob", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    assert project.name == "Acme"
    assert project.owner == user
    assert str(project) == "Acme"


@pytest.mark.django_db
def test_task_defaults_and_choices():
    user = User.objects.create_user(username="carol", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    task = Task.objects.create(project=project, title="Write tests")
    assert task.priority == "medium"
    assert task.status == "todo"
    assert task.is_completed is False
    assert str(task) == "Write tests"


@pytest.mark.django_db
def test_task_assignee_optional():
    user = User.objects.create_user(username="dave", password="x")
    project = Project.objects.create(name="Acme", owner=user)
    task = Task.objects.create(project=project, title="With assignee", assignee=user)
    assert task.assignee == user


# --------------------------------------------------------------------------- #
#  AuthService
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_register_user_returns_user():
    user = AuthService.register_user("erin", "e@x.io", "secret123")
    assert isinstance(user, User)
    assert user.username == "erin"


@pytest.mark.django_db
def test_authenticate_success():
    AuthService.register_user("frank", "f@x.io", "secret123")
    result = AuthService.authenticate_user("frank", "secret123")
    assert result is not None
    assert "access" in result and "refresh" in result
    assert result["username"] == "frank"


@pytest.mark.django_db
def test_authenticate_wrong_password():
    AuthService.register_user("george", "g@x.io", "secret123")
    assert AuthService.authenticate_user("george", "wrong") is None


@pytest.mark.django_db
def test_authenticate_unknown_user():
    assert AuthService.authenticate_user("ghost", "x") is None


@pytest.mark.django_db
def test_oauth_login_creates_user():
    result = AuthService.oauth_login("google", "tok123abc")
    assert result["created"] is True
    assert "access" in result


@pytest.mark.django_db
def test_oauth_login_returns_existing():
    AuthService.oauth_login("google", "tok456def")
    second = AuthService.oauth_login("google", "tok456def")
    assert second["created"] is False


@pytest.mark.django_db
def test_refresh_invalid_token_returns_none():
    assert AuthService.refresh_tokens("not-a-real-token") is None
