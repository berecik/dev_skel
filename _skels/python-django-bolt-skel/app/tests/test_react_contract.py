import json

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User

from app.api import ItemViewSet, react_state_delete, react_state_load, react_state_upsert
from app.models import Item, ReactState


class DummyRequest:
    def __init__(self, body: dict | None = None):
        self.body = json.dumps(body or {}).encode('utf-8')


@pytest.mark.django_db
def test_item_viewset_list_create_and_complete_round_trip():
    viewset = ItemViewSet()

    created = async_to_sync(viewset.create)(
        DummyRequest(
            {
                'name': 'wrapper item',
                'description': 'created from django-bolt contract test',
                'is_completed': False,
            }
        )
    )

    assert created.status_code == 201
    created_payload = created.data
    assert created_payload.name == 'wrapper item'
    assert created_payload.is_completed is False

    listed = async_to_sync(viewset.list)(DummyRequest())
    assert [item.name for item in listed] == ['wrapper item']

    retrieved = async_to_sync(viewset.retrieve)(DummyRequest(), pk=created_payload.id)
    assert retrieved.description == 'created from django-bolt contract test'

    completed = async_to_sync(viewset.complete.fn)(viewset, DummyRequest(), pk=created_payload.id)
    assert completed.is_completed is True
    assert Item.objects.get(pk=created_payload.id).is_completed is True


@pytest.mark.django_db
def test_react_state_endpoints_isolate_users(monkeypatch):
    alice = User.objects.create_user(username='alice-react', password='x')
    bob = User.objects.create_user(username='bob-react', password='x')

    async def current_alice(request):
        return alice

    async def current_bob(request):
        return bob

    monkeypatch.setattr('app.api.get_current_user', current_alice)
    async_to_sync(react_state_upsert)(DummyRequest({'value': {'filter': 'mine'}}), 'items')

    monkeypatch.setattr('app.api.get_current_user', current_bob)
    async_to_sync(react_state_upsert)(DummyRequest({'value': {'filter': 'all'}}), 'items')

    bob_payload = async_to_sync(react_state_load)(DummyRequest())
    assert bob_payload == {'items': {'filter': 'all'}}

    monkeypatch.setattr('app.api.get_current_user', current_alice)
    alice_payload = async_to_sync(react_state_load)(DummyRequest())
    assert alice_payload == {'items': {'filter': 'mine'}}

    deleted = async_to_sync(react_state_delete)(DummyRequest(), 'items')
    assert deleted == {'key': 'items', 'deleted': True}
    assert ReactState.objects.filter(user=alice, key='items').count() == 0
    assert ReactState.objects.filter(user=bob, key='items').count() == 1
