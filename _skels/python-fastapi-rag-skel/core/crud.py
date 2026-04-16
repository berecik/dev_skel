from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from .repository import AbstractRepository, ModelType

CrudType = TypeVar("CrudType", bound="CRUDBase")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, repository: AbstractRepository):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD) and extra list.

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.repository = repository

    def __len__(self) -> int:
        return len(self.repository)

    def list(self) -> list[ModelType]:
        return self.repository.list()

    def get(self, id: Any) -> Optional[ModelType]:
        return self.repository.get(id)

    def create(self, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        self.repository.add(db_obj)
        return db_obj

    def update(
            self,
            obj_in: Union[UpdateSchemaType,
            Dict[str, Any]],
            id: Any
    ) -> ModelType:
        return self._update(obj_in, id)

    def _update(
            self,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]],
            id: Any | None = None,
            db_obj: ModelType | None = None
    ) -> ModelType:
        if id:
            db_obj = self.get(id=id)
        assert db_obj is not None
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        self.repository.add(db_obj)
        return db_obj

    def remove(self, id: Any) -> bool:
        result = self.repository.delete(id)
        return result

    @property
    def model(self) -> Type[ModelType]:
        return self.repository.model

    def commit(self):
        raise NotImplementedError

    def rollback(self):
        raise NotImplementedError

    def refresh(self, obj):
        raise NotImplementedError

