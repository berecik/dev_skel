from __future__ import annotations

import re
from abc import abstractmethod

from typing import TypeVar, Generic
from pydantic import BaseModel
# from fastapi_events.dispatcher import dispatch

ModelType = TypeVar("ModelType", bound=BaseModel)


class Event:
    """Base class for domain events"""
    pass


class Command:
    """Base class for domain commands"""
    pass


class BaseEvent(Generic[ModelType]):
    kwargs: dict
    obj: ModelType

    def __init__(self, obj: ModelType, **kwargs):
        self.obj = obj
        self.kwargs = kwargs

    @classmethod
    @property
    def __event_name__(cls):
        class_name = cls.__name__
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
        name = name.replace('_event', '')
        return name

    @property
    def name(self):
        return self.__event_name__

    def dispatch(self, **kwargs):
        self._dispatch(**kwargs)

    @abstractmethod
    def _dispatch(self, **kwargs):
        ...


# class FastApiEvent(BaseEvent[ModelType]):
#     def _dispatch(self, **kwargs):
#         dispatch(self.__event_name__, self.obj, **kwargs)

#
# if __name__ == '__main__':
#     class TestModel(BaseModel):
#         id: int
#         name: str
#
#
#     class TestEvent(BaseEvent[TestModel]):
#         def _dispatch(self, **kwargs):
#             print('dispatching event:', self.__event_name__)
#             print('obj:', self.obj)
#
#
#     event = TestEvent(obj=TestModel(id=1, name='test'))
#     event.dispatch()
#     print(event.__event_name__)
#     print(event.obj)
#     print(event.__class__.__name__)
#     print(event.__event_name__)
