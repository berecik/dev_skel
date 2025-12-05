import pytest

from .testing_model import SampleModel, SampleModelCrud, SampleModelCreate, \
    SampleModelUpdate, SampleModelRepository
from .. import CRUDBase


def test_crud_base():
    crud = CRUDBase[SampleModel, SampleModelCreate, SampleModelUpdate](SampleModelRepository)
    assert crud.repository == SampleModelRepository
    with pytest.raises(NotImplementedError):
        crud.refresh(SampleModel)
    with pytest.raises(NotImplementedError):
        crud.rollback()
    with pytest.raises(NotImplementedError):
        crud.commit()


def test_create(crud: SampleModelCrud):
    create_obj = SampleModelCreate(name="test object", id=1)
    obj = crud.create(create_obj)
    crud.commit()
    assert obj.id == 1
    assert obj.name == "test object"
    assert len(crud) == 1


def test_get(crud: SampleModelCrud, obj: SampleModel):
    current_obj = crud.get(obj.id)
    assert current_obj.id == obj.id
    assert current_obj.name == obj.name


def test_update(crud: SampleModelCrud, obj: SampleModel):
    create_dict = SampleModelCreate(name="test object", id=1)
    obj.name = "new name"
    update_obj = SampleModelUpdate(**obj.model_dump())
    crud.update(obj_in=update_obj, id=obj.id)
    crud.commit()

    current_obj = crud.get(obj.id)

    assert current_obj.id == obj.id
    assert current_obj.name == "new name"


def test_update_form_dict(crud: SampleModelCrud, obj: SampleModel):
    update_dict = dict(name="new name", id=obj.id)
    crud.update(obj_in=update_dict, id=obj.id)
    crud.commit()

    current_obj = crud.get(obj.id)

    assert current_obj.id == obj.id
    assert current_obj.name == "new name"


def test_delete(crud: SampleModelCrud, obj: SampleModel):
    removed = crud.remove(id=obj.id)
    assert removed is True
    assert len(crud) == 0
