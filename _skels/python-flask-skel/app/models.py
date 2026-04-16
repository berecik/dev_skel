"""SQLAlchemy models for the wrapper-shared backend stack.

Schemas mirror the django-bolt skeleton's ``app/models.py`` so a single
``_shared/db.sqlite3`` is interchangeable across every dev_skel
backend (Python: django, django-bolt, fastapi, flask; JVM: spring;
Rust: actix, axum). The React frontend's typed fetch client + JWT
auth flow consumes the same shape regardless of which backend is
serving it.
"""

from datetime import datetime

from app import db


class User(db.Model):
    """Wrapper-shared user account.

    Backs ``/api/auth/register`` and ``/api/auth/login``. The password
    is stored as a bcrypt hash; ``email`` is captured for completeness
    (the React skel asks for it on register) but not used for auth.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(255), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Item(db.Model):
    """Wrapper-shared CRUD resource consumed by React via ``/api/items``."""

    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(2048), nullable=True)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Serialise to the wrapper-shared snake_case JSON shape."""

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_completed": bool(self.is_completed),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReactState(db.Model):
    """Per-user JSON KV store backing the React ``useAppState`` hook.

    The wire format the React frontend uses (see
    ``ts-react-skel/src/state/state-api.ts``) stores values as opaque
    JSON strings, so the backend never has to know the shape.
    """

    __tablename__ = "react_state"
    __table_args__ = (
        db.UniqueConstraint("user_id", "key", name="uq_react_state_user_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
