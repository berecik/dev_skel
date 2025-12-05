import pytest

from .testing_model import SampleModel, SampleModelRepository, FakeSampleModelRepository


@pytest.fixture(name="repository")
def get_repository() -> SampleModelRepository:
    return FakeSampleModelRepository(SampleModel)


@pytest.fixture(name="create_obj")
def create_obj(repository: SampleModelRepository) -> SampleModel:
    create_obj = SampleModel(name="test object", id=1)
    repository.add(create_obj)
    return create_obj


def test_repository():
    repo = FakeSampleModelRepository(SampleModel)
    assert repo.say() == "repository"
    assert issubclass(FakeSampleModelRepository, SampleModelRepository)
    assert isinstance(repo, SampleModelRepository)


def test_create(repository: SampleModelRepository):
    create_obj = SampleModel(name="test object", id=1)
    repository.add(create_obj)
    assert len(repository) == 1


def test_get(repository: SampleModelRepository, create_obj: SampleModel):
    obj = repository.get(create_obj.id)
    assert obj.id == create_obj.id
    assert obj.name == create_obj.name


def test_update(repository: SampleModelRepository, create_obj: SampleModel):
    create_obj.name = "new name"
    repository.add(create_obj)

    current_obj = repository.get(create_obj.id)

    assert current_obj.id == create_obj.id
    assert current_obj.name == "new name"


def test_delete(repository: SampleModelRepository, create_obj: SampleModel):
    removed = repository.delete(id=create_obj.id)
    assert removed is True
    assert len(repository) == 0


def test_delete_wrong_obj(repository: SampleModelRepository):
    removed = repository.delete(id=666)
    assert removed is False
