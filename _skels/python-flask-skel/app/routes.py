"""HTTP routes for the wrapper-shared backend stack.

Five blueprints expose the canonical contract every dev_skel backend
honours so the React frontend's typed fetch client + JWT auth flow
(``ts-react-skel/src/api/items.ts`` + ``src/state/state-api.ts``) Just
Works against this Flask service:

* ``/api/auth/register`` and ``/api/auth/login``
* ``/api/categories`` CRUD
* ``/api/items`` CRUD + ``POST /api/items/<id>/complete``
* ``/api/state`` per-user JSON KV store

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
from app.models import Category, Item, ReactState, User


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
