"""Tests for the wrapper-shared backend stack.

Exercises the canonical ``register → login → CRUD → reject anonymous``
flow. Mirrors the smoke that ``_bin/skel-test-react-django`` runs
over real HTTP — the unit tests catch regressions much faster.
"""

import json
import uuid

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


def _register(client, username=None, password="alice-password-1234"):
    if username is None:
        username = "u-" + uuid.uuid4().hex[:8]
    body = {
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
        "password_confirm": password,
    }
    return client.post(
        "/api/auth/register",
        data=json.dumps(body),
        content_type="application/json",
    )


def _login(client, username, password="alice-password-1234"):
    return client.post(
        "/api/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_index_returns_project_info(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["project"] == "python-django-skel"
    assert body["framework"] == "Django"


@pytest.mark.django_db
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.django_db
def test_register_login_returns_jwt(client):
    register = _register(client, "alice")
    assert register.status_code == 201, register.content
    body = register.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["id"]
    assert body["access"]
    assert body["refresh"]

    login = _login(client, "alice")
    assert login.status_code == 200, login.content
    assert login.json()["user_id"] == body["user"]["id"]


@pytest.mark.django_db
def test_duplicate_register_is_409(client):
    assert _register(client, "carol").status_code == 201
    assert _register(client, "carol").status_code == 409


@pytest.mark.django_db
def test_items_require_jwt(client):
    response = client.get("/api/items")
    assert response.status_code == 401


@pytest.mark.django_db
def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/items",
        HTTP_AUTHORIZATION="Bearer not-a-real-token",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_full_items_flow(client):
    register = _register(client, "dave")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    listed = client.get("/api/items", **auth)
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/api/items",
        data=json.dumps({"name": "first", "description": "hi", "is_completed": False}),
        content_type="application/json",
        **auth,
    )
    assert created.status_code == 201, created.content
    item = created.json()
    assert item["name"] == "first"
    assert item["is_completed"] is False

    fetched = client.get(f"/api/items/{item['id']}", **auth)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "first"

    completed = client.post(f"/api/items/{item['id']}/complete", **auth)
    assert completed.status_code == 200
    assert completed.json()["is_completed"] is True


@pytest.mark.django_db
def test_full_categories_flow(client):
    register = _register(client, "frank")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    listed = client.get("/api/categories", **auth)
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/api/categories",
        data=json.dumps({"name": "Work", "description": "Work items"}),
        content_type="application/json",
        **auth,
    )
    assert created.status_code == 201, created.content
    cat = created.json()
    assert cat["name"] == "Work"
    assert cat["description"] == "Work items"
    assert "id" in cat
    assert "created_at" in cat
    assert "updated_at" in cat

    fetched = client.get(f"/api/categories/{cat['id']}", **auth)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Work"

    updated = client.put(
        f"/api/categories/{cat['id']}",
        data=json.dumps({"name": "Personal", "description": "Personal items"}),
        content_type="application/json",
        **auth,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Personal"

    deleted = client.delete(f"/api/categories/{cat['id']}", **auth)
    assert deleted.status_code == 204


@pytest.mark.django_db
def test_categories_require_jwt(client):
    response = client.get("/api/categories")
    assert response.status_code == 401


@pytest.mark.django_db
def test_item_with_category(client):
    register = _register(client, "grace")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    cat = client.post(
        "/api/categories",
        data=json.dumps({"name": "Errands"}),
        content_type="application/json",
        **auth,
    )
    cat_id = cat.json()["id"]

    created = client.post(
        "/api/items",
        data=json.dumps({"name": "Buy milk", "category_id": cat_id}),
        content_type="application/json",
        **auth,
    )
    assert created.status_code == 201, created.content
    assert created.json()["category_id"] == cat_id

    created_no_cat = client.post(
        "/api/items",
        data=json.dumps({"name": "Standalone"}),
        content_type="application/json",
        **auth,
    )
    assert created_no_cat.status_code == 201
    assert created_no_cat.json()["category_id"] is None


@pytest.mark.django_db
def test_state_roundtrip(client):
    register = _register(client, "eve")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    initial = client.get("/api/state", **auth)
    assert initial.status_code == 200
    assert initial.json() == {}

    saved = client.put(
        "/api/state/items.showCompleted",
        data=json.dumps({"value": "true"}),
        content_type="application/json",
        **auth,
    )
    assert saved.status_code == 200

    after = client.get("/api/state", **auth)
    assert after.json() == {"items.showCompleted": "true"}

    deleted = client.delete("/api/state/items.showCompleted", **auth)
    assert deleted.status_code == 200

    final = client.get("/api/state", **auth)
    assert final.json() == {}
