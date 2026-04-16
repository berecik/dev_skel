import chromadb
from langchain_chroma import Chroma

from .config import RagSettings
from .embeddings import get_embeddings_from_settings

_vectorstore: Chroma | None = None


def get_vectorstore(settings: RagSettings) -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        client = chromadb.PersistentClient(
            path=str(settings.get_chroma_path()),
        )
        embeddings = get_embeddings_from_settings(settings)
        _vectorstore = Chroma(
            client=client,
            collection_name=settings.chroma_collection,
            embedding_function=embeddings,
        )
    return _vectorstore


def reset_vectorstore() -> None:
    global _vectorstore
    _vectorstore = None
