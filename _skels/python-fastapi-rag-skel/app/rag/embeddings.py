from functools import lru_cache

from langchain_core.embeddings import Embeddings

from .config import RagSettings


@lru_cache(maxsize=2)
def get_embeddings(provider: str, model: str) -> Embeddings:
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model)

    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_embeddings_from_settings(settings: RagSettings) -> Embeddings:
    if settings.embedding_provider == "openai":
        return get_embeddings("openai", settings.openai_embedding_model)
    return get_embeddings("huggingface", settings.embedding_model)
