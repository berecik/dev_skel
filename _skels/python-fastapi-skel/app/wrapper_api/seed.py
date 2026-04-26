"""Seed default user accounts from environment variables at startup.

Reads six env vars (three per account):

* ``USER_LOGIN``, ``USER_EMAIL``, ``USER_PASSWORD`` -- regular user
* ``SUPERUSER_LOGIN``, ``SUPERUSER_EMAIL``, ``SUPERUSER_PASSWORD`` -- admin

If *all three* vars for an account are set and no ``WrapperUser`` with
that username exists yet, the account is created. Otherwise the account
is silently skipped, making the function safe to call on every startup.
"""

from __future__ import annotations

import logging
import os

from sqlmodel import Session, select

from .db import WrapperUser
from .security import hash_password

logger = logging.getLogger(__name__)


def seed_default_accounts(session: Session) -> None:
    """Create default user and superuser accounts when env vars are set."""

    _seed_account(
        session,
        username=os.environ.get("USER_LOGIN", ""),
        email=os.environ.get("USER_EMAIL", ""),
        password=os.environ.get("USER_PASSWORD", ""),
        is_superuser=False,
        label="default user",
    )
    _seed_account(
        session,
        username=os.environ.get("SUPERUSER_LOGIN", ""),
        email=os.environ.get("SUPERUSER_EMAIL", ""),
        password=os.environ.get("SUPERUSER_PASSWORD", ""),
        is_superuser=True,
        label="superuser",
    )
    session.commit()


def _seed_account(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
    is_superuser: bool,
    label: str,
) -> None:
    if not (username and email and password):
        logger.debug("Skipping %s seed: env vars not fully set", label)
        return

    existing = session.exec(
        select(WrapperUser).where(WrapperUser.username == username)
    ).first()
    if existing is not None:
        logger.debug("Skipping %s seed: username %r already exists", label, username)
        return

    user = WrapperUser(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        is_superuser=is_superuser,
    )
    session.add(user)
    logger.info("Seeded %s account: %s <%s>", label, username, email)
