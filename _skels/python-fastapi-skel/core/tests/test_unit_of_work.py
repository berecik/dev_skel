from .testing_model import SampleModel, SampleModelUnitOfWork, FakeSampleModelUnitOfWork, FakeSampleModelRepository, \
    SampleModelCrud, SampleModelCreate


def test_unit_of_work():
    uow = FakeSampleModelUnitOfWork()
    assert uow.repository.say() == "repository"
    assert issubclass(FakeSampleModelUnitOfWork, SampleModelUnitOfWork)
    assert isinstance(uow, SampleModelUnitOfWork)
    assert uow.model_type == SampleModel
    assert uow.repository_type == FakeSampleModelRepository
    assert uow.crud_type == SampleModelCrud


def test_context_of_uow():
    uow = FakeSampleModelUnitOfWork()
    with uow as crud:
        assert isinstance(crud, SampleModelCrud)
        assert crud.model == SampleModel
        assert isinstance(crud.repository, FakeSampleModelRepository)


def test_create_by_uow():
    uow = FakeSampleModelUnitOfWork()
    with uow as crud:
        create_obj = SampleModelCreate(name="test object", id=1)
        obj = crud.create(create_obj)
        crud.commit()
        assert crud.say() == "crud repository"
        assert obj.id == 1
        assert obj.name == "test object"
        assert len(crud) == 1
