from typing import List, Optional
from sqlmodel import Field, SQLModel

from ..models import ExampleItemBase, ExampleItemRepository, ExampleItemCrud, ExampleItemUnitOfWork

from core.adapters.sql import SqlAlchemyRepository
from core.adapters.sql import SqlAlchemyUnitOfWork


class ExampleItem(ExampleItemBase, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")


class ExampleItemSqlRepository(SqlAlchemyRepository, ExampleItemRepository):
    def filter_by_owner(self, owner_id: int) -> List[ExampleItem]:
        return (
            self._query()
            .filter(self.model.owner_id == owner_id)
        )


class ExampleItemSqlUnitOfWork(ExampleItemUnitOfWork, SqlAlchemyUnitOfWork):
    repository_type = ExampleItemSqlRepository
    crud_type = ExampleItemCrud
    model_type = ExampleItem


def get_example_item_uow(**kwargs) -> ExampleItemUnitOfWork:
    return ExampleItemSqlUnitOfWork(ExampleItem, ExampleItemCrud, **kwargs)
