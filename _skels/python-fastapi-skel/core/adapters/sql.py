from __future__ import annotations

from typing import Type

from fastapi import Query
from sqlalchemy import Engine, create_engine, StaticPool
from sqlalchemy.orm import sessionmaker, Session
from sqlmodel import SQLModel

import config
from core.unit_of_work import AbstractUnitOfWork
from core.repository import AbstractRepository


class SqlAlchemyRepository(AbstractRepository):
    def __init__(self, model: Type[SQLModel], session):
        super().__init__(model)
        self.session = session

    def _add(self, obj):
        self.session.add(obj)

    def _get(self, id):
        return self._query().filter(self.model.id == id).first()

    def _query(self) -> Query:
        return self.session.query(self._model)

    def _delete(self, id):
        obj = self._get(id)
        if obj:
            self.session.delete(obj)
            return True
        return False

    def __len__(self):
        return self._query().count()


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):

    session_factory: sessionmaker
    session: Session | None = None
    repository_type: Type[SqlAlchemyRepository]
    model_type: Type[SQLModel]

    def __init__(self, model: Type[SQLModel] = None, crud=None, session_factory=None,
                 repository=None, uri: str | None = None):
        super().__init__(model, crud, repository)
        if uri is None:
            uri = config.SQLALCHEMY_DATABASE_URI
        if session_factory is None:
            self.session_factory = sessionmaker(
                bind=engine_factory(uri)
            )
        else:
            self.session_factory = session_factory

    def __enter__(self):
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session.close()

    def _commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def refresh(self, obj):
        if not self.session:
            raise ValueError("No session")
        self.session.refresh(obj)

    @property
    def repository(self):
        self.session = self.session_factory()
        return self.repository_type(self.model_type, self.session)


def engine_factory(uri: str) -> Engine:
    engine = create_engine(uri, echo=True)
    SQLModel.metadata.create_all(engine)
    return engine


def session_factory():
    pass


def testing_session_factory():
    engine = create_engine(
        config.SQLALCHEMY_DATABASE_TEST_URI, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)
