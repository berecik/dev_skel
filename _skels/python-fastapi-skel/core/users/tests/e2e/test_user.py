from starlette.testclient import TestClient

from core.users import UserBase, UserCrud, UserCreate


def test_user_me_endpoint(anon_client: TestClient, user: UserBase, users: UserCrud, token: str):
    response = anon_client.get("/user/me")
    assert response.status_code == 401

    response = anon_client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    users.remove(id=user.id)

    response = anon_client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_user_create_endpoint(anon_client: TestClient, token: str, supertoken: str):
    new_user = UserCreate(email="ala@ma.kota.pl", password="test", is_superuser=True)

    response = anon_client.post("/user/", json=new_user.model_dump(), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400

    response = anon_client.post("/user/", json=new_user.model_dump(), headers={"Authorization": f"Bearer {supertoken}"})
    assert response.status_code == 200