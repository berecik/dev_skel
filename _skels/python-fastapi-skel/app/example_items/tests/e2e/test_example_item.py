from fastapi.testclient import TestClient

import config
from app.example_items.models import ExampleItemCrud, ExampleItemCreate, ExampleItemBase
from core.users import UserBase


def test_api_create_example_item(
        client: TestClient,
        example_item_create: ExampleItemCreate,
        user: UserBase
):
    example_item_json = example_item_create.model_dump()
    response = client.post(
        f"{config.API_PREFIX}/example_items/",
        json=example_item_json
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == example_item_create.title
    assert data["owner_id"] == user.id
    assert "id" in data


def test_api_get_user_example_item(
        client: TestClient,
        user_example_item: ExampleItemBase,
        user: UserBase
):
    response = client.get(f"{config.API_PREFIX}/example_items/{user_example_item.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == user_example_item.title
    assert "id" in data
    assert data["id"] == user_example_item.id
    assert data["owner_id"] == user.id


def test_api_get_not_owned_example_item(
        client: TestClient,
        example_item: ExampleItemBase,
        example_items: ExampleItemCrud
):
    example_item.owner_id = 666
    example_items.update(example_item, example_item.id)
    example_items.commit()
    response = client.get(f"{config.API_PREFIX}/example_items/{ example_item.id }")
    assert response.status_code == 400


def test_api_get_example_item(superclient: TestClient, example_item: ExampleItemBase):
    response = superclient.get(f"{config.API_PREFIX}/example_items/{ example_item.id }")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == example_item.title
    assert "id" in data
    assert data["id"] == example_item.id


def test_api_get_non_exist_example_item(superclient: TestClient, example_item: ExampleItemBase):
    response = superclient.get(f"{config.API_PREFIX}/example_items/666")
    assert response.status_code == 404


def test_api_put_example_item(
        client: TestClient,
        user_example_item: ExampleItemBase,
        example_items: ExampleItemCrud
):
    example_item_json = user_example_item.model_dump()
    example_item_json["title"] = "new title"
    response = client.put(
        f"{config.API_PREFIX}/example_items/{user_example_item.id}",
        json=example_item_json
    )
    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "new title"
    assert "id" in data
    assert data["id"] == user_example_item.id

    changed_example_item = example_items.get(user_example_item.id)
    assert changed_example_item.title == "new title"
    assert changed_example_item.id == user_example_item.id


def test_api_put_example_item_superuser(
        superclient: TestClient,
        example_item: ExampleItemBase,
        example_items: ExampleItemCrud
):
    example_item_json = example_item.model_dump()
    example_item_json["title"] = "new title"
    response = superclient.put(
        f"{config.API_PREFIX}/example_items/{ example_item.id }",
        json=example_item_json
    )
    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "new title"
    assert "id" in data
    assert data["id"] == example_item.id

    changed_example_item = example_items.get(example_item.id)
    assert changed_example_item.title == "new title"
    assert changed_example_item.id == example_item.id


def test_api_put_wrong_example_item(
        superclient: TestClient,
        example_item: ExampleItemBase,
        example_items: ExampleItemCrud
):
    example_item_json = example_item.model_dump()
    example_item_json["title"] = "new title"
    response = superclient.put(
        f"{config.API_PREFIX}/example_items/666",
        json=example_item_json
    )
    assert response.status_code == 404


def test_api_put_now_owned_example_item(
        client: TestClient,
        example_item: ExampleItemBase,
        example_items: ExampleItemCrud
):
    example_item_json = example_item.model_dump()
    example_item_json["title"] = "new title"
    response = client.put(
        f"{config.API_PREFIX}/example_items/{ example_item.id }",
        json=example_item_json
    )
    assert response.status_code == 400


def test_api_get_example_items_list(superclient: TestClient, example_item: ExampleItemBase):
    response = superclient.get(f"{config.API_PREFIX}/example_items/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    incoming_example_item = data[0]
    assert incoming_example_item["title"] == example_item.title
    assert "id" in incoming_example_item
    assert incoming_example_item["id"] == example_item.id


def test_api_get_user_example_items_list(client: TestClient, user_example_item: ExampleItemBase):
    response = client.get(f"{config.API_PREFIX}/example_items/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    incoming_example_item = data[0]
    assert incoming_example_item["title"] == user_example_item.title
    assert "id" in incoming_example_item
    assert incoming_example_item["id"] == user_example_item.id


def test_api_delete_example_item(
        client: TestClient,
        user_example_item: ExampleItemBase,
        example_items: ExampleItemCrud
):
    response = client.delete(f"{config.API_PREFIX}/example_items/{user_example_item.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == user_example_item.id
    assert example_items.get(user_example_item.id) is None
    assert len(example_items) == 0


def test_api_delete_not_owned_example_item(client: TestClient, example_item: ExampleItemBase):
    response = client.delete(f"{config.API_PREFIX}/example_items/{ example_item.id }")
    assert response.status_code == 400


def test_api_delete_wrong_example_item(client: TestClient):
    response = client.delete(f"{config.API_PREFIX}/example_items/666")
    assert response.status_code == 404
