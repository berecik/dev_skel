"""Application routes."""

from flask import Blueprint, jsonify, request

from app import db
from app.models import Item

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    """Root endpoint returning project info."""
    return jsonify({
        "project": "python-flask-skel",
        "version": "1.0.0",
        "framework": "Flask",
        "status": "running",
    })


@bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@bp.route("/api/items", methods=["GET"])
def list_items():
    """List all items."""
    items = Item.query.all()
    return jsonify([item.to_dict() for item in items])


@bp.route("/api/items", methods=["POST"])
def create_item():
    """Create a new item."""
    data = request.get_json()
    item = Item(
        name=data["name"],
        description=data.get("description"),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@bp.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    """Get an item by ID."""
    item = Item.query.get_or_404(item_id)
    return jsonify(item.to_dict())
