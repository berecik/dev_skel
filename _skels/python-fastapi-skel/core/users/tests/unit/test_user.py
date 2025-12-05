from core.users.db import UserCrud
from core.users.models import UserBase, UserCreate


def test_create_user(users: UserCrud, user_create: UserCreate):
    current_user = users.create(user_create)
    users.commit()
    assert current_user.id == 1
    assert current_user.email == user_create.email
    assert current_user.is_active == user_create.is_active
    assert current_user.is_superuser == user_create.is_superuser
    assert len(users) == 1


def test_get_by_email_user(user: UserBase, users: UserCrud, user_create: UserCreate):
    user_test = users.get_by_email(user.email)
    assert user.id == user_test.id
    assert user_test.email == user_create.email


def test_authenticate_user(user: UserBase, users: UserCrud, user_create: UserCreate):
    user_test = users.authenticate(user.email, user_create.password)
    assert user_test.id == user.id
    assert user_test.email == user.email


def test_get_user(user: UserBase, users: UserCrud):
    user = users.get(user.id)
    assert user.id == user.id
    assert user.email == user.email
    assert user.is_active == user.is_active
    assert user.is_superuser == user.is_superuser
