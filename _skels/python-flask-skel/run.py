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
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
