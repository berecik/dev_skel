#!/usr/bin/env python
"""Run the Flask application."""

import os

from app import create_app, db

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized.")


if __name__ == "__main__":
    # Honour the wrapper-shared `SERVICE_PORT` env var (set by
    # <wrapper>/.env via the dispatch scripts) before falling back to
    # `PORT` and the per-service default. The same precedence rules
    # the actix / axum / spring skels use so multi-service wrappers
    # can run several Flask backends on different ports without
    # per-service edits.
    port = int(os.getenv("SERVICE_PORT") or os.getenv("PORT") or 5000)
    host = os.getenv("SERVICE_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=True)
