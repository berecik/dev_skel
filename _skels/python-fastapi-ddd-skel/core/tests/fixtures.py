import asyncio
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.deps import get_users_crud, get_current_user, get_current_active_superuser
from core.security import create_access_token
from core.tests.utils import get_test_session
from core.users.db import UserUnitOfWork, UserCrud
from core.users.models import UserBase, UserCreate
from core.users.tests.testing_user import UserUnitOfWorkTest, user_create_data
from main import get_app


@pytest.fixture(name="users_uow")
def users_uow_fixture() -> UserUnitOfWork:
    yield UserUnitOfWorkTest()


@pytest.fixture(name="users")
def users_crud_fixture(users_uow: UserUnitOfWork) -> UserCrud:
    with users_uow as users:
        yield users


@pytest.fixture(name="user_create")
def user_create_obj():
    return UserCreate(**user_create_data)


@pytest.fixture(name="superuser_create")
def superuser_create_obj(user_create: UserCreate):
    user_create.is_superuser = True
    user_create.email = f"super{user_create.email}"
    _create_data = user_create.model_dump()
    return UserCreate(**_create_data)


@pytest.fixture(name="user_inactive_create")
def user_inactive_create_obj(user_create: UserCreate):
    user_create.is_active = False
    user_create.email = f"inactive{user_create.email}"
    _create_data = user_create.model_dump()
    return UserCreate(**_create_data)


@pytest.fixture(name="user")
def create_user(users: UserCrud, user_create: UserCreate) -> UserBase:
    user = users.create(user_create, update_if_exist=True)
    users.commit()
    yield user


@pytest.fixture(name="user_inactive")
def create_inactive_user(users: UserCrud, user_inactive_create: UserCreate) -> UserBase:
    user = users.create(user_inactive_create, update_if_exist=True)
    users.commit()
    yield user


@pytest.fixture(name="superuser")
def create_superuser(users: UserCrud, superuser_create: UserCreate) -> UserBase:
    superuser = users.create(superuser_create)
    users.commit()
    yield superuser


@pytest.fixture(name="app_dependencies")
def get_app_dependencies():
    return []


@pytest.fixture(name="test_app")
def get_test_app(users: UserCrud, app_dependencies: list):
    def get_crud():
        return users

    app = get_app()

    app.dependency_overrides[get_users_crud] = get_crud

    for origin, override in app_dependencies:
        app.dependency_overrides[origin] = override

    yield app
    app.dependency_overrides.clear()


@pytest.fixture(name="anon_client")
def get_client(users: UserCrud, test_app: FastAPI):
    client = TestClient(test_app, backend_options={'loop_factory': asyncio.new_event_loop})

    yield client


@pytest.fixture(name="client")
def get_auth_client(test_app: FastAPI, user: UserBase):
    def get_user():
        return user

    test_app.dependency_overrides[get_current_user] = get_user

    client = TestClient(test_app, backend_options={'loop_factory': asyncio.new_event_loop})

    yield client


@pytest.fixture(name="superclient")
def get_super_client(test_app: FastAPI, superuser: UserBase):
    def get_superuser():
        return superuser

    test_app.dependency_overrides[get_current_user] = get_superuser
    test_app.dependency_overrides[get_current_active_superuser] = get_superuser

    client = TestClient(test_app, backend_options={'loop_factory': asyncio.new_event_loop})

    yield client


@pytest.fixture(name="token")
def get_token(user: UserBase):
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )
    yield access_token


@pytest.fixture(name="supertoken")
def get_supertoken(superuser: UserBase):
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        superuser.id, expires_delta=access_token_expires
    )
    yield access_token


@pytest.fixture(name="session")
def session_fixture():
    with get_test_session() as session:
        yield session


