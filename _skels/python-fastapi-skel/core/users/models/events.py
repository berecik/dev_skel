from core.events import BaseEvent
from .user import UserBase, UserCreate, UserUpdate


class UserLoginEvent(BaseEvent[UserBase]):
    ...
    # __event_name__ = 'USER_LOGIN'


class UserCreateEvent(BaseEvent[UserCreate]):
    ...
    # __event_name__ = 'USER_CREATE'


class UserUpdateEvent(BaseEvent[UserUpdate]):
    ...
    # __event_name__ = 'USER_UPDATE'