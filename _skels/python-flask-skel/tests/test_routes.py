"""Tests for the wrapper-shared backend stack.

Exercises the canonical ``register → login → CRUD → reject anonymous``
flow against an in-memory SQLite database. Mirrors the smoke that
``_bin/skel-test-react-flask`` runs over real HTTP — the unit tests
catch regressions much faster.
"""

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

    fetched = client.get(f"/api/items/{item['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.get_json()["name"] == "first"

    completed = client.post(f"/api/items/{item['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.get_json()["is_completed"] is True


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
