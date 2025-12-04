"""Tests for routes."""

import pytest

from app import create_app, db
from app.config import TestConfig


@pytest.fixture
def app():
    """Create test application."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_index_returns_project_info(client):
    """Test index endpoint returns project information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert data["project"] == "python-flask-skel"
    assert data["framework"] == "Flask"


def test_health_endpoint(client):
    """Test health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"


def test_create_and_get_item(client):
    """Test creating and retrieving an item."""
    # Create item
    response = client.post(
        "/api/items",
        json={"name": "Test Item", "description": "A test item"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Test Item"

    # Get item
    item_id = data["id"]
    response = client.get(f"/api/items/{item_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "Test Item"
