from typing import Any, TypeVar, Generic
from pydantic import BaseModel
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from core import AbstractRepository, AbstractUnitOfWork

ModelType = TypeVar("ModelType", bound=BaseModel)


class FakeRepository(Generic[ModelType], AbstractRepository[ModelType]):
    __objects: list[ModelType]

    def __init__(self, model):
        super().__init__(model)
        self.__objects = []

    def _add(self, obj: ModelType):
        db_obj = self._get(obj.id)

        if db_obj is not None:
            i = self.__objects.index(db_obj)
            self.__objects[i] = obj
        else:
            id = len(self.__objects) + 1
            obj.id = id
            self.__objects.append(obj)

    def _get(self, id: int) -> Any | None:
        for item in self.__objects:
            if item.id == id:
                return item
        return None

    def _query(self) -> list[ModelType]:
        return self.__objects

    def _delete(self, id: int) -> bool:
        for i, item in enumerate(self.__objects):
            if item.id == id:
                self.__objects.pop(i)
                return True
        return False


class FakeUnitOfWork(AbstractUnitOfWork):
    def _commit(self):
        pass


def get_test_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


