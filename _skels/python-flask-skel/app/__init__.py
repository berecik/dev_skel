"""Flask application factory.

Wires the wrapper-shared backend stack: SQLAlchemy + Flask-Migrate +
the five blueprints (root / auth / categories / items / state). Tables
are created on startup via ``db.create_all()`` so the canonical
``register → login → CRUD`` flow works against a freshly-generated
wrapper without a separate migrations step. Use Flask-Migrate
(``flask db migrate``) for production deployments where schema
changes need to be versioned.
"""

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event

from app.config import Config

db = SQLAlchemy()
migrate = Migrate()


def _enable_sqlite_fks(dbapi_connection, _connection_record):
    """Enable SQLite foreign key enforcement (required for ON DELETE SET NULL)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    # Enable SQLite FK enforcement when the URI points at SQLite.
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        with app.app_context():
            event.listen(db.engine, "connect", _enable_sqlite_fks)

    # Imported lazily so the blueprint module can `from app import db`
    # at top level without triggering a circular import.
    from app import models  # noqa: F401 — registers SQLAlchemy mappers
    from app.routes import auth_bp, categories_bp, items_bp, root_bp, state_bp

    app.register_blueprint(root_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(state_bp)

    # Bootstrap the wrapper-shared schema on startup. SQLAlchemy's
    # ``create_all`` is a no-op when the tables already exist, so this
    # is safe to call on every restart and does not interfere with
    # Flask-Migrate's versioned migrations.
    with app.app_context():
        db.create_all()

    return app
