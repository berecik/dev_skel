from typing import Annotated

from fastapi import Depends

from .models import DocumentUnitOfWork
from .adapters.sql import get_document_uow, DocumentCrud

DocumentsUowDep = Annotated[DocumentUnitOfWork, Depends(get_document_uow)]


def get_documents_crud(documents_uow: DocumentsUowDep) -> DocumentCrud:
    with documents_uow as documents:
        yield documents


DocumentsDep = Annotated[DocumentCrud, Depends(get_documents_crud)]
