from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings


class RagSettings(BaseSettings):
    model_config = {"env_prefix": "RAG_"}

    # Embedding
    embedding_provider: Literal["huggingface", "openai"] = "huggingface"
    embedding_model: str = "all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # LLM
    llm_provider: Literal["ollama", "openai"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_temperature: float = 0.3
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Document chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "documents"

    # Upload
    upload_dir: str = "./uploads"

    # Retrieval
    top_k: int = 5

    # Conversation history
    history_backend: Literal["memory", "sqlite"] = "memory"
    history_max_turns: int = 10

    # WebSocket auth
    ws_auth: Literal["required", "optional"] = "optional"

    def get_upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_chroma_path(self) -> Path:
        p = Path(self.chroma_persist_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


_settings: RagSettings | None = None


def get_rag_settings() -> RagSettings:
    global _settings
    if _settings is None:
        _settings = RagSettings()
    return _settings
