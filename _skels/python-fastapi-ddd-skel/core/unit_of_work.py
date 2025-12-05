# pylint: disable=attribute-defined-outside-init
from __future__ import annotations

import abc
from typing import Type, Generic

from pydantic import BaseModel
from sqlalchemy import create_engine, Engine
from sqlmodel import SQLModel

from .crud import CRUDBase, CrudType
from .repository import AbstractRepository


class AbstractUnitOfWork(Generic[CrudType]):
    crud_type: CrudType
    repository_type: Type[AbstractRepository]
    model_type: Type[BaseModel]

    def __init__(
            self,
            model: Type[BaseModel] = None,
            crud: Type[CRUDBase] = None,
            repository: Type[AbstractRepository] | None = None,
    ):
        if repository is not None:
            self.repository_type = repository
        elif self.repository_type is None:
            raise ValueError("No repository type")

        if crud is not None:
            self.crud_type = crud
        elif self.crud_type is None:
            raise ValueError("No crud type")

        if model is not None:
            self.model_type = model
        elif self.model_type is None:
            raise ValueError("No model type")

    def __enter__(self) -> CRUDBase:
        return self.crud

    def __exit__(self, *args):
        self.commit()

    def commit(self):
        self._commit()

    @abc.abstractmethod
    def _commit(self):
        raise NotImplementedError

    def rollback(self):
        pass

    def refresh(self, obj):
        pass

    @property
    def repository(self):
        return self.repository_type(self.model_type)

    @property
    def crud(self):
        crud = self.crud_type(self.repository)
        crud.commit = self.commit
        crud.rollback = self.rollback
        crud.refresh = self.refresh
        return crud


def engine_factory(uri: str) -> Engine:
    engine = create_engine(uri, echo=True)
    SQLModel.metadata.create_all(engine)
    return engine
