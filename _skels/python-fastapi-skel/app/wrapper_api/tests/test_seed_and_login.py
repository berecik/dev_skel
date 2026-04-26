"""Tests for default-account seeding and login-by-email-or-username.

Each test uses an in-memory SQLite database so the tests are fully
isolated and do not touch any on-disk state.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.wrapper_api.db import WrapperUser
from app.wrapper_api.security import hash_password
from app.wrapper_api.seed import seed_default_accounts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> Session:
    """Return a Session backed by a fresh in-memory SQLite database."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[WrapperUser.__table__])
    return Session(engine, autoflush=False, expire_on_commit=False)


def _create_user(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
    is_superuser: bool = False,
) -> WrapperUser:
    user = WrapperUser(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        is_superuser=is_superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

def _get_test_client(session: Session):
    """Build a TestClient whose auth routes use the provided session."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.wrapper_api.auth import router as auth_router
    from app.wrapper_api.db import get_session

    app = FastAPI()
    app.include_router(auth_router)

    def _override_session():
        yield session

    app.dependency_overrides[get_session] = _override_session
    return TestClient(app)


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_creates_default_user(monkeypatch):
    """seed_default_accounts creates a regular user from USER_* env vars."""
    monkeypatch.setenv("USER_LOGIN", "user")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")
    monkeypatch.setenv("USER_PASSWORD", "secret")
    # Ensure superuser vars are absent so only the regular user is created.
    monkeypatch.delenv("SUPERUSER_LOGIN", raising=False)
    monkeypatch.delenv("SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("SUPERUSER_PASSWORD", raising=False)

    session = _make_session()
    seed_default_accounts(session)

    from sqlmodel import select
    user = session.exec(
        select(WrapperUser).where(WrapperUser.username == "user")
    ).first()
    assert user is not None
    assert user.email == "user@example.com"
    assert user.is_superuser is False


def test_seed_creates_superuser(monkeypatch):
    """seed_default_accounts creates a superuser from SUPERUSER_* env vars."""
    monkeypatch.delenv("USER_LOGIN", raising=False)
    monkeypatch.delenv("USER_EMAIL", raising=False)
    monkeypatch.delenv("USER_PASSWORD", raising=False)
    monkeypatch.setenv("SUPERUSER_LOGIN", "admin")
    monkeypatch.setenv("SUPERUSER_EMAIL", "admin@example.com")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "secret")

    session = _make_session()
    seed_default_accounts(session)

    from sqlmodel import select
    admin = session.exec(
        select(WrapperUser).where(WrapperUser.username == "admin")
    ).first()
    assert admin is not None
    assert admin.email == "admin@example.com"
    assert admin.is_superuser is True


def test_seed_is_idempotent(monkeypatch):
    """Running seed twice does not duplicate accounts."""
    monkeypatch.setenv("USER_LOGIN", "user")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")
    monkeypatch.setenv("USER_PASSWORD", "secret")
    monkeypatch.delenv("SUPERUSER_LOGIN", raising=False)
    monkeypatch.delenv("SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("SUPERUSER_PASSWORD", raising=False)

    session = _make_session()
    seed_default_accounts(session)
    seed_default_accounts(session)  # second call -- should be a no-op

    from sqlmodel import select
    users = session.exec(
        select(WrapperUser).where(WrapperUser.username == "user")
    ).all()
    assert len(users) == 1


# ---------------------------------------------------------------------------
# Login-by-username and login-by-email tests
# ---------------------------------------------------------------------------

def test_login_by_username(monkeypatch):
    """Login with a username returns 200 and valid tokens."""
    monkeypatch.setenv("USER_LOGIN", "user")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")
    monkeypatch.setenv("USER_PASSWORD", "secret")
    monkeypatch.delenv("SUPERUSER_LOGIN", raising=False)
    monkeypatch.delenv("SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("SUPERUSER_PASSWORD", raising=False)

    session = _make_session()
    seed_default_accounts(session)
    client = _get_test_client(session)

    resp = client.post("/api/auth/login", json={"username": "user", "password": "secret"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access" in data
    assert "refresh" in data
    assert data["username"] == "user"


def test_login_by_email(monkeypatch):
    """Login with an email address returns 200 and valid tokens."""
    monkeypatch.setenv("USER_LOGIN", "user")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")
    monkeypatch.setenv("USER_PASSWORD", "secret")
    monkeypatch.delenv("SUPERUSER_LOGIN", raising=False)
    monkeypatch.delenv("SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("SUPERUSER_PASSWORD", raising=False)

    session = _make_session()
    seed_default_accounts(session)
    client = _get_test_client(session)

    resp = client.post(
        "/api/auth/login",
        json={"username": "user@example.com", "password": "secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access" in data
    assert data["username"] == "user"


def test_superuser_login_by_username(monkeypatch):
    """Superuser can log in by username."""
    monkeypatch.delenv("USER_LOGIN", raising=False)
    monkeypatch.delenv("USER_EMAIL", raising=False)
    monkeypatch.delenv("USER_PASSWORD", raising=False)
    monkeypatch.setenv("SUPERUSER_LOGIN", "admin")
    monkeypatch.setenv("SUPERUSER_EMAIL", "admin@example.com")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "secret")

    session = _make_session()
    seed_default_accounts(session)
    client = _get_test_client(session)

    resp = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_superuser_login_by_email(monkeypatch):
    """Superuser can log in by email."""
    monkeypatch.delenv("USER_LOGIN", raising=False)
    monkeypatch.delenv("USER_EMAIL", raising=False)
    monkeypatch.delenv("USER_PASSWORD", raising=False)
    monkeypatch.setenv("SUPERUSER_LOGIN", "admin")
    monkeypatch.setenv("SUPERUSER_EMAIL", "admin@example.com")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "secret")

    session = _make_session()
    seed_default_accounts(session)
    client = _get_test_client(session)

    resp = client.post(
        "/api/auth/login",
        json={"username": "admin@example.com", "password": "secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
