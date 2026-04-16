from abc import ABC
from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel

from core import AbstractUnitOfWork, AbstractRepository, CRUDBase


class DocumentStatus(str, Enum):
    pending = "pending"
    indexed = "indexed"
    error = "error"


class DocumentBase(BaseModel):
    id: Optional[int] = None
    filename: str = ""
    content_type: str = ""
    file_size: int = 0
    chunk_count: int = 0
    status: DocumentStatus = DocumentStatus.pending
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentCreate(BaseModel):
    filename: str
    content_type: str
    file_size: int


class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    chunk_count: Optional[int] = None


class DocumentRepository(AbstractRepository, ABC):
    def filter_by_status(self, status: DocumentStatus) -> List[DocumentBase]:
        return [d for d in self.list() if d.status == status]


class DocumentCrud(CRUDBase[DocumentBase, DocumentCreate, DocumentUpdate]):
    repository: DocumentRepository

    def get_by_status(self, status: DocumentStatus) -> List[DocumentBase]:
        return self.repository.filter_by_status(status)


class DocumentUnitOfWork(AbstractUnitOfWork[DocumentCrud], ABC):
    repository_type = DocumentRepository
    crud_type = DocumentCrud
    model_type = DocumentBase
