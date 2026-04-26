"""Seed default user accounts from env vars on startup."""

import logging
import os

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


def seed_default_accounts() -> None:
    """Create USER_LOGIN and SUPERUSER_LOGIN if they don't exist."""
    User = get_user_model()
    accounts = [
        {
            "username": os.environ.get("USER_LOGIN", "user"),
            "email": os.environ.get("USER_EMAIL", "user@example.com"),
            "password": os.environ.get("USER_PASSWORD", "secret"),
            "is_superuser": False,
        },
        {
            "username": os.environ.get("SUPERUSER_LOGIN", "admin"),
            "email": os.environ.get("SUPERUSER_EMAIL", "admin@example.com"),
            "password": os.environ.get("SUPERUSER_PASSWORD", "secret"),
            "is_superuser": True,
        },
    ]
    for acct in accounts:
        username = acct["username"]
        if User.objects.filter(username=username).exists():
            logger.info("[seed] Default user '%s' already exists", username)
            continue
        user = User.objects.create_user(
            username=username,
            email=acct["email"],
            password=acct["password"],
        )
        user.is_superuser = acct["is_superuser"]
        user.is_staff = acct["is_superuser"]
        user.save(update_fields=["is_superuser", "is_staff"])
        logger.info("[seed] Created default user '%s'", username)
