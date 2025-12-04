"""Tests for views."""

import pytest
from django.test import Client


@pytest.fixture
def client():
    """Create test client."""
    return Client()


@pytest.mark.django_db
def test_index_returns_project_info(client):
    """Test index endpoint returns project information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "python-django-skel"
    assert data["framework"] == "Django"


@pytest.mark.django_db
def test_health_endpoint(client):
    """Test health endpoint returns healthy status."""
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
