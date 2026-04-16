from abc import ABC

from pydantic import BaseModel

from . import FakeRepository, FakeUnitOfWork
from .. import AbstractRepository, CRUDBase, AbstractUnitOfWork


class SampleModel(BaseModel):
    id: int
    name: str


class SampleModelCreate(SampleModel):
    ...


class SampleModelUpdate(SampleModel):
    ...


class SampleModelRepository(AbstractRepository, ABC):
    def say(self):
        return "repository"


class SampleModelCrud(CRUDBase[SampleModel, SampleModelCreate, SampleModelUpdate]):
    repository: SampleModelRepository

    def say(self):
        return f"crud {self.repository.say()}"


class FakeSampleModelRepository(FakeRepository[SampleModel], SampleModelRepository):
    ...


class SampleModelUnitOfWork(AbstractUnitOfWork[SampleModelCrud], ABC):
    repository_type = SampleModelRepository
    crud_type = SampleModelCrud
    model_type = SampleModel


class FakeSampleModelUnitOfWork(FakeUnitOfWork, SampleModelUnitOfWork):
    repository_type = FakeSampleModelRepository
