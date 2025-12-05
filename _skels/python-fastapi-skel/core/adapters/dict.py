from __future__ import annotations

from typing import Type

from fastapi import Query
from pydantic import BaseModel

from core import AbstractUnitOfWork, AbstractRepository


class DictRepository(AbstractRepository):
    def __init__(self, model: Type[BaseModel], session: dict):
        super().__init__(model)
        self.session = session

    def _add(self, obj):
        id = len(self) + 1
        self.session[id] = obj

    def _get(self, id) -> BaseModel | None:
        return self.session.get(id, None)

    def _query(self) -> Query:
        return self.session.values()

    def _delete(self, id):
        obj = self._get(id)
        if obj:
            del self.session[id]
            return True
        return False

    def __len__(self):
        return len(self.session)


class DictUnitOfWork(AbstractUnitOfWork):
    session: dict = {}
    repository_type = DictRepository
    model_type: Type[BaseModel]

    def __init__(self, model: Type[BaseModel], crud, session=None):
        super().__init__(model, crud, repository=self.repository_type)
        if session is not None:
            self.session = session

    def __enter__(self):
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session = {}

    def _commit(self):
        pass

    def rollback(self):
        pass

    def refresh(self, obj):
        pass

    @property
    def repository(self):
        return self.repository_type(self.model_type, self.session)
