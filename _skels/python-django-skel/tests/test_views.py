"""Tests for the wrapper-shared backend stack.

Exercises the canonical ``register → login → CRUD → reject anonymous``
flow. Mirrors the smoke that ``_bin/skel-test-react-django`` runs
over real HTTP — the unit tests catch regressions much faster.
"""

import json
import uuid

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


def _register(client, username=None, password="alice-password-1234"):
    if username is None:
        username = "u-" + uuid.uuid4().hex[:8]
    body = {
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
        "password_confirm": password,
    }
    return client.post(
        "/api/auth/register",
        data=json.dumps(body),
        content_type="application/json",
    )


def _login(client, username, password="alice-password-1234"):
    return client.post(
        "/api/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_index_returns_project_info(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["project"] == "python-django-skel"
    assert body["framework"] == "Django"


@pytest.mark.django_db
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.django_db
def test_register_login_returns_jwt(client):
    register = _register(client, "alice")
    assert register.status_code == 201, register.content
    body = register.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["id"]
    assert body["access"]
    assert body["refresh"]

    login = _login(client, "alice")
    assert login.status_code == 200, login.content
    assert login.json()["user_id"] == body["user"]["id"]


@pytest.mark.django_db
def test_duplicate_register_is_409(client):
    assert _register(client, "carol").status_code == 201
    assert _register(client, "carol").status_code == 409


@pytest.mark.django_db
def test_items_require_jwt(client):
    response = client.get("/api/items")
    assert response.status_code == 401


@pytest.mark.django_db
def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/items",
        HTTP_AUTHORIZATION="Bearer not-a-real-token",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_full_items_flow(client):
    register = _register(client, "dave")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    listed = client.get("/api/items", **auth)
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/api/items",
        data=json.dumps({"name": "first", "description": "hi", "is_completed": False}),
        content_type="application/json",
        **auth,
    )
    assert created.status_code == 201, created.content
    item = created.json()
    assert item["name"] == "first"
    assert item["is_completed"] is False

    fetched = client.get(f"/api/items/{item['id']}", **auth)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "first"

    completed = client.post(f"/api/items/{item['id']}/complete", **auth)
    assert completed.status_code == 200
    assert completed.json()["is_completed"] is True


@pytest.mark.django_db
def test_full_categories_flow(client):
    register = _register(client, "frank")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    listed = client.get("/api/categories", **auth)
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/api/categories",
        data=json.dumps({"name": "Work", "description": "Work items"}),
        content_type="application/json",
        **auth,
    )
    assert created.status_code == 201, created.content
    cat = created.json()
    assert cat["name"] == "Work"
    assert cat["description"] == "Work items"
    assert "id" in cat
    assert "created_at" in cat
    assert "updated_at" in cat

    fetched = client.get(f"/api/categories/{cat['id']}", **auth)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Work"

    updated = client.put(
        f"/api/categories/{cat['id']}",
        data=json.dumps({"name": "Personal", "description": "Personal items"}),
        content_type="application/json",
        **auth,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Personal"

    deleted = client.delete(f"/api/categories/{cat['id']}", **auth)
    assert deleted.status_code == 204


@pytest.mark.django_db
def test_categories_require_jwt(client):
    response = client.get("/api/categories")
    assert response.status_code == 401


@pytest.mark.django_db
def test_item_with_category(client):
    register = _register(client, "grace")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    cat = client.post(
        "/api/categories",
        data=json.dumps({"name": "Errands"}),
        content_type="application/json",
        **auth,
    )
    cat_id = cat.json()["id"]

    created = client.post(
        "/api/items",
        data=json.dumps({"name": "Buy milk", "category_id": cat_id}),
        content_type="application/json",
        **auth,
    )
    assert created.status_code == 201, created.content
    assert created.json()["category_id"] == cat_id

    created_no_cat = client.post(
        "/api/items",
        data=json.dumps({"name": "Standalone"}),
        content_type="application/json",
        **auth,
    )
    assert created_no_cat.status_code == 201
    assert created_no_cat.json()["category_id"] is None


@pytest.mark.django_db
def test_state_roundtrip(client):
    register = _register(client, "eve")
    token = register.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    initial = client.get("/api/state", **auth)
    assert initial.status_code == 200
    assert initial.json() == {}

    saved = client.put(
        "/api/state/items.showCompleted",
        data=json.dumps({"value": "true"}),
        content_type="application/json",
        **auth,
    )
    assert saved.status_code == 200

    after = client.get("/api/state", **auth)
    assert after.json() == {"items.showCompleted": "true"}

    deleted = client.delete("/api/state/items.showCompleted", **auth)
    assert deleted.status_code == 200

    final = client.get("/api/state", **auth)
    assert final.json() == {}


@pytest.mark.django_db
def test_default_user_can_login(client):
    from app.seed import seed_default_accounts
    seed_default_accounts()
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "user", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "access" in resp.json()


@pytest.mark.django_db
def test_default_superuser_can_login(client):
    from app.seed import seed_default_accounts
    seed_default_accounts()
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "admin", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "access" in resp.json()


@pytest.mark.django_db
def test_login_by_email(client):
    from app.seed import seed_default_accounts
    seed_default_accounts()
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "user@example.com", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "access" in resp.json()


@pytest.mark.django_db
def test_login_by_email_superuser(client):
    from app.seed import seed_default_accounts
    seed_default_accounts()
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "admin@example.com", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "access" in resp.json()


# --------------------------------------------------------------------------- #
#  Order workflow tests
# --------------------------------------------------------------------------- #


def _create_catalog_item(client, auth, name="Widget", price=9.99):
    """Helper: create a catalog item and return its JSON."""
    resp = client.post(
        "/api/catalog",
        data=json.dumps({"name": name, "price": price}),
        content_type="application/json",
        **auth,
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


@pytest.mark.django_db
def test_order_workflow(client):
    """Full happy path: create catalog item, draft order, add lines,
    set address, submit, approve."""
    # Register and get auth token
    reg = _register(client, "order_user")
    token = reg.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    # 1. Create catalog items
    widget = _create_catalog_item(client, auth, "Widget", 9.99)
    gadget = _create_catalog_item(client, auth, "Gadget", 19.99)

    # Verify catalog list
    catalog = client.get("/api/catalog", **auth)
    assert catalog.status_code == 200
    assert len(catalog.json()) == 2

    # Verify catalog detail
    detail = client.get(f"/api/catalog/{widget['id']}", **auth)
    assert detail.status_code == 200
    assert detail.json()["name"] == "Widget"

    # 2. Create draft order
    order_resp = client.post("/api/orders", content_type="application/json", **auth)
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] == "draft"
    order_id = order["id"]

    # 3. Add lines
    line1 = client.post(
        f"/api/orders/{order_id}/lines",
        data=json.dumps({"catalog_item_id": widget["id"], "quantity": 3}),
        content_type="application/json",
        **auth,
    )
    assert line1.status_code == 201
    assert line1.json()["quantity"] == 3
    assert line1.json()["unit_price"] == 9.99

    line2 = client.post(
        f"/api/orders/{order_id}/lines",
        data=json.dumps({"catalog_item_id": gadget["id"], "quantity": 1}),
        content_type="application/json",
        **auth,
    )
    assert line2.status_code == 201

    # 4. Delete a line
    del_resp = client.delete(f"/api/orders/{order_id}/lines/{line2.json()['id']}", **auth)
    assert del_resp.status_code == 200

    # 5. Set address
    addr_resp = client.put(
        f"/api/orders/{order_id}/address",
        data=json.dumps({
            "street": "123 Main St",
            "city": "Springfield",
            "zip_code": "62701",
            "phone": "555-1234",
            "notes": "Ring bell",
        }),
        content_type="application/json",
        **auth,
    )
    assert addr_resp.status_code == 200
    assert addr_resp.json()["city"] == "Springfield"

    # 6. Verify order detail (nested lines + address)
    detail = client.get(f"/api/orders/{order_id}", **auth)
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["lines"]) == 1
    assert body["address"]["street"] == "123 Main St"

    # 7. Submit (draft -> pending)
    submit_resp = client.post(f"/api/orders/{order_id}/submit", **auth)
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "pending"
    assert submit_resp.json()["submitted_at"] is not None

    # 8. Approve
    approve_resp = client.post(
        f"/api/orders/{order_id}/approve",
        data=json.dumps({"wait_minutes": 30, "feedback": "looks good"}),
        content_type="application/json",
        **auth,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"
    assert approve_resp.json()["wait_minutes"] == 30
    assert approve_resp.json()["feedback"] == "looks good"

    # 9. Verify orders list
    orders_list = client.get("/api/orders", **auth)
    assert orders_list.status_code == 200
    assert len(orders_list.json()) == 1
    assert orders_list.json()[0]["status"] == "approved"


@pytest.mark.django_db
def test_order_reject(client):
    """Reject path: create order, submit, reject with feedback."""
    reg = _register(client, "reject_user")
    token = reg.json()["access"]
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    # Create a catalog item and order with a line
    item = _create_catalog_item(client, auth, "Doohickey", 5.00)
    order_resp = client.post("/api/orders", content_type="application/json", **auth)
    order_id = order_resp.json()["id"]

    client.post(
        f"/api/orders/{order_id}/lines",
        data=json.dumps({"catalog_item_id": item["id"], "quantity": 1}),
        content_type="application/json",
        **auth,
    )

    # Submit
    submit = client.post(f"/api/orders/{order_id}/submit", **auth)
    assert submit.status_code == 200
    assert submit.json()["status"] == "pending"

    # Reject
    reject = client.post(
        f"/api/orders/{order_id}/reject",
        data=json.dumps({"feedback": "out of stock"}),
        content_type="application/json",
        **auth,
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"
    assert reject.json()["feedback"] == "out of stock"

    # Cannot submit again (not draft)
    re_submit = client.post(f"/api/orders/{order_id}/submit", **auth)
    assert re_submit.status_code == 400
