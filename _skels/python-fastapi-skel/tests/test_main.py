"""Tests for main application."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_returns_project_info(client):
    """Test root endpoint returns project information."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "python-fastapi-skel"
    assert data["framework"] == "FastAPI"


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test health endpoint returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
