from datetime import datetime
from typing import Optional, List

from sqlmodel import Field, SQLModel

from ..models import (
    DocumentBase,
    DocumentRepository,
    DocumentCrud,
    DocumentUnitOfWork,
    DocumentStatus,
)
from core.adapters.sql import SqlAlchemyRepository, SqlAlchemyUnitOfWork


class Document(DocumentBase, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(max_length=512)
    content_type: str = Field(max_length=128, default="")
    file_size: int = Field(default=0)
    chunk_count: int = Field(default=0)
    status: DocumentStatus = Field(default=DocumentStatus.pending)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentSqlRepository(SqlAlchemyRepository, DocumentRepository):
    def filter_by_status(self, status: DocumentStatus) -> List[Document]:
        return self._query().filter(self.model.status == status).all()


class DocumentSqlUnitOfWork(DocumentUnitOfWork, SqlAlchemyUnitOfWork):
    repository_type = DocumentSqlRepository
    crud_type = DocumentCrud
    model_type = Document


def get_document_uow(**kwargs) -> DocumentUnitOfWork:
    return DocumentSqlUnitOfWork(Document, DocumentCrud, **kwargs)
