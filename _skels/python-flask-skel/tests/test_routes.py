"""Tests for the wrapper-shared backend stack.

Exercises the canonical ``register → login → CRUD → reject anonymous``
flow against an in-memory SQLite database. Mirrors the smoke that
``_bin/skel-test-react-flask`` runs over real HTTP — the unit tests
catch regressions much faster.
"""

import os

import pytest

from app import create_app, db
from app.config import TestConfig


@pytest.fixture
def app():
    """Create test application backed by in-memory SQLite."""

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_seeded_app(env_vars):
    """Create an app with the given env vars set for seeding."""

    old = {}
    for key, value in env_vars.items():
        old[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        app = create_app(TestConfig)
    finally:
        for key, prev in old.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, username="alice", email="alice@example.com", password="alice-password"):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password,
        },
    )
    return response


def _login(client, username="alice", password="alice-password"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _auth_headers(client):
    """Register + login and return Bearer headers."""
    _register(client)
    token = _login(client).get_json()["access"]
    return {"Authorization": f"Bearer {token}"}


def test_index_returns_project_info(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert data["project"] == "python-flask-skel"
    assert data["framework"] == "Flask"


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}


def test_register_and_login_returns_jwt(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["id"]
    assert body["access"]
    assert body["refresh"]

    login = _login(client)
    assert login.status_code == 200
    assert login.get_json()["user_id"] == body["user"]["id"]


def test_duplicate_register_is_409(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409


def test_items_require_jwt(client):
    response = client.get("/api/items")
    assert response.status_code == 401
    assert response.get_json()["status"] == 401


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/items",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_full_items_flow(client):
    assert _register(client).status_code == 201
    token = _login(client).get_json()["access"]
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/api/items", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json() == []

    created = client.post(
        "/api/items",
        json={"name": "first", "description": "hi", "is_completed": False},
        headers=headers,
    )
    assert created.status_code == 201
    item = created.get_json()
    assert item["name"] == "first"
    assert item["is_completed"] is False
    assert item["category_id"] is None

    fetched = client.get(f"/api/items/{item['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.get_json()["name"] == "first"

    completed = client.post(f"/api/items/{item['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.get_json()["is_completed"] is True


# --------------------------------------------------------------------------- #
#  Categories CRUD
# --------------------------------------------------------------------------- #


def test_categories_require_jwt(client):
    response = client.get("/api/categories")
    assert response.status_code == 401


def test_categories_crud(client):
    headers = _auth_headers(client)

    # List — initially empty
    listed = client.get("/api/categories", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json() == []

    # Create
    created = client.post(
        "/api/categories",
        json={"name": "Urgent", "description": "High-priority items"},
        headers=headers,
    )
    assert created.status_code == 201
    cat = created.get_json()
    assert cat["name"] == "Urgent"
    assert cat["description"] == "High-priority items"
    assert "id" in cat
    assert "created_at" in cat
    assert "updated_at" in cat

    # Get by id
    fetched = client.get(f"/api/categories/{cat['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.get_json()["name"] == "Urgent"

    # Update
    updated = client.put(
        f"/api/categories/{cat['id']}",
        json={"name": "Not Urgent", "description": "Low-priority"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Not Urgent"
    assert updated.get_json()["description"] == "Low-priority"

    # Delete
    deleted = client.delete(f"/api/categories/{cat['id']}", headers=headers)
    assert deleted.status_code == 204

    # Confirm gone
    gone = client.get(f"/api/categories/{cat['id']}", headers=headers)
    assert gone.status_code == 404


def test_category_duplicate_name_is_409(client):
    headers = _auth_headers(client)
    client.post("/api/categories", json={"name": "Dup"}, headers=headers)
    resp = client.post("/api/categories", json={"name": "Dup"}, headers=headers)
    assert resp.status_code == 409


def test_category_empty_name_is_400(client):
    headers = _auth_headers(client)
    resp = client.post("/api/categories", json={"name": ""}, headers=headers)
    assert resp.status_code == 400


def test_category_not_found_is_404(client):
    headers = _auth_headers(client)
    assert client.get("/api/categories/9999", headers=headers).status_code == 404
    assert client.put(
        "/api/categories/9999", json={"name": "x"}, headers=headers
    ).status_code == 404
    assert client.delete("/api/categories/9999", headers=headers).status_code == 404


# --------------------------------------------------------------------------- #
#  Items + category_id
# --------------------------------------------------------------------------- #


def test_item_with_category_id(client):
    headers = _auth_headers(client)

    # Create a category first
    cat = client.post(
        "/api/categories", json={"name": "Work"}, headers=headers
    ).get_json()

    # Create an item linked to the category
    item = client.post(
        "/api/items",
        json={"name": "task-1", "category_id": cat["id"]},
        headers=headers,
    ).get_json()
    assert item["category_id"] == cat["id"]

    # Fetch and verify
    fetched = client.get(f"/api/items/{item['id']}", headers=headers).get_json()
    assert fetched["category_id"] == cat["id"]


def test_item_category_id_null_by_default(client):
    headers = _auth_headers(client)
    item = client.post(
        "/api/items", json={"name": "no-cat"}, headers=headers
    ).get_json()
    assert item["category_id"] is None


# --------------------------------------------------------------------------- #
#  State endpoints
# --------------------------------------------------------------------------- #


def test_state_roundtrip(client):
    assert _register(client).status_code == 201
    token = _login(client).get_json()["access"]
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/state", headers=headers)
    assert initial.status_code == 200
    assert initial.get_json() == {}

    saved = client.put(
        "/api/state/items.showCompleted",
        json={"value": "true"},
        headers=headers,
    )
    assert saved.status_code == 200

    after = client.get("/api/state", headers=headers)
    assert after.status_code == 200
    assert after.get_json() == {"items.showCompleted": "true"}

    deleted = client.delete("/api/state/items.showCompleted", headers=headers)
    assert deleted.status_code == 200

    final = client.get("/api/state", headers=headers)
    assert final.get_json() == {}


# --------------------------------------------------------------------------- #
#  Seed default accounts + login by email-or-username
# --------------------------------------------------------------------------- #


def test_seed_user_login_by_username():
    """Seeded regular user can log in by username."""

    app = _make_seeded_app({
        "USER_LOGIN": "user",
        "USER_EMAIL": "user@example.com",
        "USER_PASSWORD": "secret",
    })
    with app.app_context():
        client = app.test_client()
        resp = client.post("/api/auth/login", json={
            "username": "user",
            "password": "secret",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "user"
        assert data["access"]
        db.session.remove()
        db.drop_all()


def test_seed_user_login_by_email():
    """Seeded regular user can log in by email."""

    app = _make_seeded_app({
        "USER_LOGIN": "user",
        "USER_EMAIL": "user@example.com",
        "USER_PASSWORD": "secret",
    })
    with app.app_context():
        client = app.test_client()
        resp = client.post("/api/auth/login", json={
            "username": "user@example.com",
            "password": "secret",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "user"
        assert data["access"]
        db.session.remove()
        db.drop_all()


def test_seed_superuser_login_by_username():
    """Seeded superuser can log in by username."""

    app = _make_seeded_app({
        "SUPERUSER_LOGIN": "admin",
        "SUPERUSER_EMAIL": "admin@example.com",
        "SUPERUSER_PASSWORD": "secret",
    })
    with app.app_context():
        client = app.test_client()
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "secret",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "admin"
        assert data["access"]
        db.session.remove()
        db.drop_all()


def test_seed_superuser_login_by_email():
    """Seeded superuser can log in by email."""

    app = _make_seeded_app({
        "SUPERUSER_LOGIN": "admin",
        "SUPERUSER_EMAIL": "admin@example.com",
        "SUPERUSER_PASSWORD": "secret",
    })
    with app.app_context():
        client = app.test_client()
        resp = client.post("/api/auth/login", json={
            "username": "admin@example.com",
            "password": "secret",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "admin"
        assert data["access"]
        db.session.remove()
        db.drop_all()
