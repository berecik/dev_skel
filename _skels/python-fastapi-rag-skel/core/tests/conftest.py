import pytest

from core.tests.testing_model import FakeSampleModelUnitOfWork, SampleModelCreate, SampleModelCrud


@pytest.fixture(name="crud")
def get_crud():
    uow = FakeSampleModelUnitOfWork()
    with uow as crud:
        yield crud


@pytest.fixture(name="create_obj")
def get_create_obj():
    return SampleModelCreate(name="test object", id=1)


@pytest.fixture(name="obj")
def get_obj(crud: SampleModelCrud, create_obj: SampleModelCreate):
    obj = crud.create(create_obj)
    crud.commit()
    return obj
