from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, BackgroundTasks

from .depts import DocumentsDep
from .models import DocumentBase, DocumentCreate, DocumentUpdate, DocumentStatus
from app.rag.config import get_rag_settings
from app.rag.depts import VectorStoreDep, RagSettingsDep
from app.rag.ingestion import ingest_document, delete_document_vectors, SUPPORTED_EXTENSIONS

router = APIRouter()


def _ingest_background(
    file_path: Path,
    doc_id: int,
    filename: str,
    settings_dict: dict,
) -> None:
    from app.rag.config import RagSettings
    from app.rag.vectorstore import get_vectorstore

    settings = RagSettings(**settings_dict)
    store = get_vectorstore(settings)
    try:
        chunk_count = ingest_document(file_path, doc_id, filename, settings, store)
        # Update document status via direct SQL (background task has no DI)
        from app.documents.adapters.sql import get_document_uow

        with get_document_uow() as crud:
            crud.update(
                obj_in=DocumentUpdate(status=DocumentStatus.indexed, chunk_count=chunk_count),
                id=doc_id,
            )
    except Exception:
        from app.documents.adapters.sql import get_document_uow

        with get_document_uow() as crud:
            crud.update(obj_in=DocumentUpdate(status=DocumentStatus.error), id=doc_id)


@router.post("/", response_model=DocumentBase, status_code=201)
def upload_document(
    file: UploadFile,
    documents: DocumentsDep,
    settings: RagSettingsDep,
    store: VectorStoreDep,
) -> Any:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    upload_dir = settings.get_upload_path()
    content = file.file.read()
    file_size = len(content)

    doc = documents.create(
        DocumentCreate(
            filename=file.filename or "unknown",
            content_type=file.content_type or "",
            file_size=file_size,
        )
    )

    file_path = upload_dir / f"{doc.id}_{file.filename}"
    file_path.write_bytes(content)

    try:
        chunk_count = ingest_document(file_path, doc.id, doc.filename, settings, store)
        doc = documents.update(
            obj_in=DocumentUpdate(status=DocumentStatus.indexed, chunk_count=chunk_count),
            id=doc.id,
        )
    except Exception:
        doc = documents.update(
            obj_in=DocumentUpdate(status=DocumentStatus.error),
            id=doc.id,
        )

    return doc


@router.get("/", response_model=list[DocumentBase])
def list_documents(
    documents: DocumentsDep,
    status: Optional[DocumentStatus] = None,
) -> Any:
    if status:
        return documents.get_by_status(status)
    return documents.list()


@router.get("/{doc_id}", response_model=DocumentBase)
def get_document(documents: DocumentsDep, doc_id: int) -> Any:
    doc = documents.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", response_model=DocumentBase)
def delete_document(
    doc_id: int,
    documents: DocumentsDep,
    settings: RagSettingsDep,
    store: VectorStoreDep,
) -> Any:
    doc = documents.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_document_vectors(doc_id, store)

    upload_dir = settings.get_upload_path()
    file_path = upload_dir / f"{doc.id}_{doc.filename}"
    if file_path.exists():
        file_path.unlink()

    documents.remove(doc.id)
    return doc
