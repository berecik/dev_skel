"""Seed default user accounts from environment variables at startup.

Creates a regular user and a superuser if the corresponding env vars
are set and the accounts do not already exist.  Uses the same
``hash_password`` helper as ``/api/auth/register`` so the stored hashes
are interchangeable.

Env vars
--------
USER_LOGIN, USER_EMAIL, USER_PASSWORD       — default regular user
SUPERUSER_LOGIN, SUPERUSER_EMAIL, SUPERUSER_PASSWORD — default superuser
"""

import os

from app import db
from app.auth import hash_password
from app.models import User


def seed_default_accounts() -> None:
    """Create default user and superuser accounts from env vars.

    Skips creation when the username already exists or the required env
    vars are not set.  Safe to call on every startup — existing rows are
    never modified.
    """

    _seed_account(
        username=os.environ.get("USER_LOGIN", "").strip(),
        email=os.environ.get("USER_EMAIL", "").strip(),
        password=os.environ.get("USER_PASSWORD", "").strip(),
    )

    _seed_account(
        username=os.environ.get("SUPERUSER_LOGIN", "").strip(),
        email=os.environ.get("SUPERUSER_EMAIL", "").strip(),
        password=os.environ.get("SUPERUSER_PASSWORD", "").strip(),
    )


def _seed_account(*, username: str, email: str, password: str) -> None:
    """Insert a single account if the username is provided and new."""

    if not username or not password:
        return

    existing = db.session.query(User).filter_by(username=username).first()
    if existing is not None:
        return

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    db.session.add(user)
    db.session.commit()
