"""HTTP routes for the wrapper-shared backend stack.

Six blueprints expose the canonical contract every dev_skel backend
honours so the React frontend's typed fetch client + JWT auth flow
(``ts-react-skel/src/api/items.ts`` + ``src/state/state-api.ts``) Just
Works against this Flask service:

* ``/api/auth/register`` and ``/api/auth/login``
* ``/api/categories`` CRUD
* ``/api/items`` CRUD + ``POST /api/items/<id>/complete``
* ``/api/state`` per-user JSON KV store
* ``/api/catalog`` + ``/api/orders`` order workflow

Plus ``/`` and ``/health`` for project info / liveness.
"""

from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth import (
    hash_password,
    jwt_required,
    mint_access_token,
    mint_refresh_token,
    verify_password,
)
from app.models import CatalogItem, Category, Item, Order, OrderAddress, OrderLine, ReactState, User


# --------------------------------------------------------------------------- #
#  Root + health
# --------------------------------------------------------------------------- #

root_bp = Blueprint("root", __name__)


@root_bp.route("/")
def index():
    """Root endpoint returning project info."""

    return jsonify({
        "project": "python-flask-skel",
        "version": "1.0.0",
        "framework": "Flask",
        "status": "running",
    })


@root_bp.route("/health")
def health():
    """Health check endpoint."""

    return jsonify({"status": "healthy"})


# --------------------------------------------------------------------------- #
#  /api/auth — JWT bearer auth
# --------------------------------------------------------------------------- #

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _bad_request(detail: str):
    response = jsonify({"detail": detail, "status": 400})
    response.status_code = 400
    return response


def _conflict(detail: str):
    response = jsonify({"detail": detail, "status": 409})
    response.status_code = 409
    return response


def _unauthorized(detail: str):
    response = jsonify({"detail": detail, "status": 401})
    response.status_code = 401
    return response


@auth_bp.route("/register", methods=["POST"])
def register():
    """``POST /api/auth/register`` → 201 ``{user, access, refresh}``."""

    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    password_confirm = payload.get("password_confirm")

    if not username:
        return _bad_request("username cannot be empty")
    if len(password) < 6:
        return _bad_request("password must be at least 6 characters")
    if password_confirm is not None and password_confirm != password:
        return _bad_request("password and password_confirm do not match")

    if db.session.query(User.id).filter_by(username=username).first() is not None:
        return _conflict(f"user '{username}' already exists")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    db.session.add(user)
    db.session.commit()

    response = jsonify({
        "user": {"id": user.id, "username": user.username, "email": user.email},
        "access": mint_access_token(user.id),
        "refresh": mint_refresh_token(user.id),
    })
    response.status_code = 201
    return response


@auth_bp.route("/login", methods=["POST"])
def login():
    """``POST /api/auth/login`` → 200 ``{access, refresh, user_id, username}``."""

    payload = request.get_json(silent=True) or {}
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        return _unauthorized("invalid username or password")

    if "@" in username:
        user = db.session.query(User).filter_by(email=username).first()
    else:
        user = db.session.query(User).filter_by(username=username).first()
    if user is None or not verify_password(password, user.password_hash):
        return _unauthorized("invalid username or password")

    return jsonify({
        "access": mint_access_token(user.id),
        "refresh": mint_refresh_token(user.id),
        "user_id": user.id,
        "username": user.username,
    })


# --------------------------------------------------------------------------- #
#  /api/categories — JWT-protected CRUD
# --------------------------------------------------------------------------- #

categories_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@categories_bp.route("", methods=["GET"])
@jwt_required
def list_categories():
    rows = db.session.query(Category).order_by(Category.id).all()
    return jsonify([cat.to_dict() for cat in rows])


@categories_bp.route("", methods=["POST"])
@jwt_required
def create_category():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return _bad_request("category name cannot be empty")
    cat = Category(
        name=name,
        description=payload.get("description") or "",
    )
    db.session.add(cat)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _conflict(f"Category with name '{name}' already exists")
    response = jsonify(cat.to_dict())
    response.status_code = 201
    return response


@categories_bp.route("/<int:category_id>", methods=["GET"])
@jwt_required
def get_category(category_id):
    cat = db.session.get(Category, category_id)
    if cat is None:
        response = jsonify({"detail": "Category not found", "status": 404})
        response.status_code = 404
        return response
    return jsonify(cat.to_dict())


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@jwt_required
def update_category(category_id):
    cat = db.session.get(Category, category_id)
    if cat is None:
        response = jsonify({"detail": "Category not found", "status": 404})
        response.status_code = 404
        return response
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return _bad_request("category name cannot be empty")
    cat.name = name
    cat.description = payload.get("description") or ""
    cat.updated_at = datetime.utcnow()
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _conflict(f"Category with name '{name}' already exists")
    return jsonify(cat.to_dict())


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required
def delete_category(category_id):
    cat = db.session.get(Category, category_id)
    if cat is None:
        response = jsonify({"detail": "Category not found", "status": 404})
        response.status_code = 404
        return response
    db.session.delete(cat)
    db.session.commit()
    response = jsonify({})
    response.status_code = 204
    return response


# --------------------------------------------------------------------------- #
#  /api/items — JWT-protected CRUD (no per-user scoping; matches the
#  django-bolt convention so cross-stack tests stay simple).
# --------------------------------------------------------------------------- #

items_bp = Blueprint("items", __name__, url_prefix="/api/items")


@items_bp.route("", methods=["GET"])
@jwt_required
def list_items():
    rows = db.session.query(Item).order_by(Item.created_at.desc(), Item.id.desc()).all()
    return jsonify([item.to_dict() for item in rows])


@items_bp.route("", methods=["POST"])
@jwt_required
def create_item():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return _bad_request("item name cannot be empty")
    item = Item(
        name=name,
        description=payload.get("description"),
        is_completed=bool(payload.get("is_completed")),
        category_id=payload.get("category_id"),
    )
    db.session.add(item)
    db.session.commit()
    response = jsonify(item.to_dict())
    response.status_code = 201
    return response


@items_bp.route("/<int:item_id>", methods=["GET"])
@jwt_required
def get_item(item_id):
    item = db.session.get(Item, item_id)
    if item is None:
        response = jsonify({"detail": f"item {item_id} not found", "status": 404})
        response.status_code = 404
        return response
    return jsonify(item.to_dict())


@items_bp.route("/<int:item_id>/complete", methods=["POST"])
@jwt_required
def complete_item(item_id):
    """Idempotent: completing an already-completed item is a no-op."""

    item = db.session.get(Item, item_id)
    if item is None:
        response = jsonify({"detail": f"item {item_id} not found", "status": 404})
        response.status_code = 404
        return response
    item.is_completed = True
    db.session.commit()
    return jsonify(item.to_dict())


# --------------------------------------------------------------------------- #
#  /api/state — per-user JSON KV store
# --------------------------------------------------------------------------- #

state_bp = Blueprint("state", __name__, url_prefix="/api/state")


@state_bp.route("", methods=["GET"])
@jwt_required
def list_state():
    rows = (
        db.session.query(ReactState)
        .filter_by(user_id=g.current_user.id)
        .order_by(ReactState.key)
        .all()
    )
    return jsonify({row.key: row.value for row in rows})


@state_bp.route("/<key>", methods=["PUT"])
@jwt_required
def upsert_state(key):
    payload = request.get_json(silent=True) or {}
    value = payload.get("value")
    if value is None:
        value = ""
    if not isinstance(value, str):
        return _bad_request("`value` must be a JSON string")

    row = (
        db.session.query(ReactState)
        .filter_by(user_id=g.current_user.id, key=key)
        .first()
    )
    if row is None:
        db.session.add(ReactState(user_id=g.current_user.id, key=key, value=value))
    else:
        row.value = value
    db.session.commit()
    return jsonify({"key": key})


@state_bp.route("/<key>", methods=["DELETE"])
@jwt_required
def delete_state(key):
    deleted = (
        db.session.query(ReactState)
        .filter_by(user_id=g.current_user.id, key=key)
        .delete()
    )
    db.session.commit()
    return jsonify({"deleted": deleted})


# --------------------------------------------------------------------------- #
#  /api — Order workflow (catalog, orders, lines, address, submit/approve/reject)
# --------------------------------------------------------------------------- #

orders_bp = Blueprint("orders", __name__, url_prefix="/api")


# -- Catalog ---------------------------------------------------------------- #

@orders_bp.route("/catalog", methods=["GET"])
@jwt_required
def list_catalog():
    """``GET /api/catalog`` → list all catalog items."""

    rows = db.session.query(CatalogItem).order_by(CatalogItem.id).all()
    return jsonify([item.to_dict() for item in rows])


@orders_bp.route("/catalog", methods=["POST"])
@jwt_required
def create_catalog_item():
    """``POST /api/catalog`` → create a new catalog item."""

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return _bad_request("catalog item name cannot be empty")
    item = CatalogItem(
        name=name,
        description=payload.get("description"),
        price=payload.get("price", 0),
    )
    db.session.add(item)
    db.session.commit()
    response = jsonify(item.to_dict())
    response.status_code = 201
    return response


@orders_bp.route("/catalog/<int:catalog_item_id>", methods=["GET"])
@jwt_required
def get_catalog_item(catalog_item_id):
    """``GET /api/catalog/{id}`` → single catalog item."""

    item = db.session.get(CatalogItem, catalog_item_id)
    if item is None:
        response = jsonify({"detail": "Catalog item not found", "status": 404})
        response.status_code = 404
        return response
    return jsonify(item.to_dict())


# -- Orders ----------------------------------------------------------------- #

def _not_found(detail: str):
    response = jsonify({"detail": detail, "status": 404})
    response.status_code = 404
    return response


@orders_bp.route("/orders", methods=["POST"])
@jwt_required
def create_order():
    """``POST /api/orders`` → create a new draft order for the current user."""

    order = Order(user_id=g.current_user.id, status="draft")
    db.session.add(order)
    db.session.commit()
    response = jsonify(order.to_dict())
    response.status_code = 201
    return response


@orders_bp.route("/orders", methods=["GET"])
@jwt_required
def list_orders():
    """``GET /api/orders`` → list all orders for the current user."""

    rows = (
        db.session.query(Order)
        .filter_by(user_id=g.current_user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )
    return jsonify([o.to_dict() for o in rows])


@orders_bp.route("/orders/<int:order_id>", methods=["GET"])
@jwt_required
def get_order(order_id):
    """``GET /api/orders/{id}`` → order detail with lines and address."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")
    return jsonify(order.to_dict(include_lines=True, include_address=True))


# -- Order lines ------------------------------------------------------------ #

@orders_bp.route("/orders/<int:order_id>/lines", methods=["POST"])
@jwt_required
def add_order_line(order_id):
    """``POST /api/orders/{id}/lines`` → add a line to a draft order."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")
    if order.status != "draft":
        return _bad_request("can only add lines to draft orders")

    payload = request.get_json(silent=True) or {}
    catalog_item_id = payload.get("catalog_item_id")
    if catalog_item_id is None:
        return _bad_request("catalog_item_id is required")

    catalog_item = db.session.get(CatalogItem, catalog_item_id)
    if catalog_item is None:
        return _not_found(f"catalog item {catalog_item_id} not found")

    quantity = payload.get("quantity", 1)
    if not isinstance(quantity, int) or quantity < 1:
        return _bad_request("quantity must be a positive integer")

    line = OrderLine(
        order_id=order.id,
        catalog_item_id=catalog_item.id,
        quantity=quantity,
        unit_price=payload.get("unit_price", catalog_item.price),
    )
    db.session.add(line)
    db.session.commit()
    response = jsonify(line.to_dict())
    response.status_code = 201
    return response


@orders_bp.route("/orders/<int:order_id>/lines/<int:line_id>", methods=["DELETE"])
@jwt_required
def delete_order_line(order_id, line_id):
    """``DELETE /api/orders/{id}/lines/{line_id}`` → remove a line from a draft order."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")
    if order.status != "draft":
        return _bad_request("can only remove lines from draft orders")

    line = db.session.get(OrderLine, line_id)
    if line is None or line.order_id != order.id:
        return _not_found(f"order line {line_id} not found")

    db.session.delete(line)
    db.session.commit()
    response = jsonify({})
    response.status_code = 204
    return response


# -- Order address ---------------------------------------------------------- #

@orders_bp.route("/orders/<int:order_id>/address", methods=["PUT"])
@jwt_required
def upsert_order_address(order_id):
    """``PUT /api/orders/{id}/address`` → set or update the delivery address."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")

    payload = request.get_json(silent=True) or {}

    if order.address is None:
        addr = OrderAddress(order_id=order.id)
        db.session.add(addr)
    else:
        addr = order.address

    addr.street = (payload.get("street") or "").strip()
    addr.city = (payload.get("city") or "").strip()
    addr.zip_code = (payload.get("zip_code") or "").strip()
    addr.phone = (payload.get("phone") or "").strip() or None
    addr.notes = (payload.get("notes") or "").strip() or None
    db.session.commit()
    return jsonify(addr.to_dict())


# -- Order lifecycle (submit / approve / reject) ---------------------------- #

@orders_bp.route("/orders/<int:order_id>/submit", methods=["POST"])
@jwt_required
def submit_order(order_id):
    """``POST /api/orders/{id}/submit`` → transition draft -> submitted."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")
    if order.status != "draft":
        return _bad_request("only draft orders can be submitted")
    if not order.lines:
        return _bad_request("cannot submit an order with no lines")

    order.status = "pending"
    order.submitted_at = datetime.utcnow()
    db.session.commit()
    return jsonify(order.to_dict(include_lines=True, include_address=True))


@orders_bp.route("/orders/<int:order_id>/approve", methods=["POST"])
@jwt_required
def approve_order(order_id):
    """``POST /api/orders/{id}/approve`` -> transition pending -> approved."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")
    if order.status != "pending":
        return _bad_request("only pending orders can be approved")

    payload = request.get_json(silent=True) or {}
    order.status = "approved"
    order.wait_minutes = payload.get("wait_minutes")
    order.feedback = payload.get("feedback")
    db.session.commit()
    return jsonify(order.to_dict(include_lines=True, include_address=True))


@orders_bp.route("/orders/<int:order_id>/reject", methods=["POST"])
@jwt_required
def reject_order(order_id):
    """``POST /api/orders/{id}/reject`` → transition submitted -> rejected."""

    order = db.session.get(Order, order_id)
    if order is None or order.user_id != g.current_user.id:
        return _not_found(f"order {order_id} not found")
    if order.status != "pending":
        return _bad_request("only pending orders can be rejected")

    payload = request.get_json(silent=True) or {}
    order.status = "rejected"
    order.feedback = payload.get("feedback")
    db.session.commit()
    return jsonify(order.to_dict(include_lines=True, include_address=True))
