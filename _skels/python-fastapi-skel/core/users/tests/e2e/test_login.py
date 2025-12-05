import pytest
from fastapi.testclient import TestClient

from core.users.db import UserCrud
from core.users.models import UserBase, UserCreate


@pytest.fixture(name="credentials")
def get_credentials(user: UserBase):
    return {"username": user.email, "password": "test"}


@pytest.fixture(name="credentials_inactive")
def get_inactive_credentials(user_inactive: UserBase):
    return {"username": user_inactive.email, "password": "test"}


@pytest.fixture(name="credentials_wrong")
def get_wrong_credentials(credentials):
    login_data_wrong = credentials.copy()
    login_data_wrong["password"] = "wrong"
    return login_data_wrong


def test_login(anon_client: TestClient, credentials: dict):
    response = anon_client.post("/login/access-token", data=credentials)
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"


def test_login_inactive(anon_client: TestClient, credentials_inactive: dict):
    response = anon_client.post("/login/access-token", data=credentials_inactive)
    assert response.status_code == 400


def test_login_wrong_password(anon_client: TestClient, credentials_wrong: dict):
    response = anon_client.post("/login/access-token", data=credentials_wrong)
    assert response.status_code == 400


def test_protected_endpoint(anon_client: TestClient, user: UserBase, users: UserCrud, token: str):
    response = anon_client.post("/login/test-token")
    assert response.status_code == 401

    response = anon_client.post("/login/test-token", headers={"Authorization": f"Bearer wrong-token"})
    assert response.status_code == 403

    response = anon_client.post("/login/test-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    users.remove(id=user.id)

    response = anon_client.post("/login/test-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_protected_endpoint_inactive(anon_client: TestClient, user: UserBase, users: UserCrud, token: str):
    response = anon_client.post("/login/test-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    users.update(user.id, dict(is_active=False))
    users.commit()

    response = anon_client.post("/login/test-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_superuser_endpoint(anon_client: TestClient, token: str, supertoken: str, superuser: UserBase, users: UserCrud):
    response = anon_client.post("/login/test-supertoken")
    assert response.status_code == 401

    response = anon_client.post("/login/test-supertoken", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400

    response = anon_client.post("/login/test-supertoken", headers={"Authorization": f"Bearer {supertoken}"})
    assert response.status_code == 200

    users.remove(id=superuser.id)

    response = anon_client.post("/login/test-supertoken", headers={"Authorization": f"Bearer {supertoken}"})
    assert response.status_code == 404


def test_superuser_endpoint_inactive(anon_client: TestClient, superuser: UserBase, users: UserCrud, supertoken: str):
    response = anon_client.post("/login/test-supertoken", headers={"Authorization": f"Bearer {supertoken}"})
    assert response.status_code == 200

    users.update(superuser.id, dict(is_active=False))
    users.commit()

    response = anon_client.post("/login/test-supertoken", headers={"Authorization": f"Bearer {supertoken}"})
    assert response.status_code == 400
