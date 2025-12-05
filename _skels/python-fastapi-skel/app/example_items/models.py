from abc import ABC
from typing import Optional, List

from pydantic import BaseModel

from core import AbstractUnitOfWork, AbstractRepository, CRUDBase


# Shared properties
class ExampleItemBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[int] = None
    id: Optional[int] = None


# Properties to receive on example_item creation
class ExampleItemCreate(ExampleItemBase):
    title: str


# Properties to receive on example_item update
class ExampleItemUpdate(ExampleItemBase):
    pass


class ExampleItemRepository(AbstractRepository, ABC):
    def filter_by_owner(self, owner_id: int) -> List[ExampleItemBase]:
        return list(
            filter(lambda example_item: example_item.owner_id == owner_id, self.list())
        )


class ExampleItemCrud(CRUDBase[ExampleItemBase, ExampleItemCreate, ExampleItemUpdate]):

    repository: ExampleItemRepository

    def get_by_owner(
            self, owner_id: int
    ) -> List[ExampleItemBase]:
        return self.repository.filter_by_owner(owner_id=owner_id)


class ExampleItemUnitOfWork(AbstractUnitOfWork[ExampleItemCrud], ABC):
    repository_type = ExampleItemRepository
    crud_type = ExampleItemCrud
    model_type = ExampleItemBase
