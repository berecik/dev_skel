from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import RagSettings


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def _load_file(file_path: Path) -> list[Document]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader

        return PyPDFLoader(str(file_path)).load()

    text = file_path.read_text(encoding="utf-8", errors="replace")
    return [Document(page_content=text, metadata={"source": str(file_path)})]


def ingest_document(
    file_path: Path,
    doc_id: int,
    filename: str,
    settings: RagSettings,
    vectorstore: Chroma,
) -> int:
    documents = _load_file(file_path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(documents)

    for i, chunk in enumerate(chunks):
        chunk.metadata.update({
            "doc_id": str(doc_id),
            "filename": filename,
            "chunk_index": i,
        })

    if chunks:
        vectorstore.add_documents(chunks)

    return len(chunks)


def delete_document_vectors(doc_id: int, vectorstore: Chroma) -> None:
    vectorstore._collection.delete(where={"doc_id": str(doc_id)})
