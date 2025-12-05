from fastapi.testclient import TestClient
from app.example_items.adapters.sql import get_example_item_uow

import config
from app.example_items.models import ExampleItemBase, ExampleItemUnitOfWork
from core.adapters.sql import testing_session_factory

def test_api_example_item_list(client: TestClient, user_example_item: ExampleItemBase):
    response = client.get(f"{config.API_PREFIX}/example_items/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_get_example_item_uow():
    uow = get_example_item_uow(session_factory=testing_session_factory)
    assert isinstance(uow, ExampleItemUnitOfWork)
    assert uow.repository_type.__name__ == "ExampleItemSqlRepository"
    assert uow.repository.model.__name__ == "ExampleItem"
