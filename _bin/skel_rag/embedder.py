"""HuggingFace embedding model factory.

The whole RAG agent uses one embedding model per process. We wrap the
construction in :func:`make_embeddings` and cache the result with
``functools.lru_cache`` so multiple ``RagAgent`` instances reuse the
same loaded model.

The dependency on ``langchain-huggingface`` (which transitively pulls
``sentence-transformers``) is imported lazily so the package can be
imported without it installed — handy for unit tests that exercise
chunking + corpus discovery in isolation.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from skel_rag.config import RagConfig

logger = logging.getLogger("skel_rag.embedder")


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend cannot be loaded."""


@lru_cache(maxsize=2)
def _make_embeddings_cached(
    model_name: str, cache_folder: str
) -> Any:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
    except ImportError as exc:
        raise EmbeddingError(
            "langchain-huggingface is not installed. Run "
            "`make install-rag-deps` to enable the RAG agent."
        ) from exc

    logger.info(
        "loading embedding model %s (cache_folder=%s)", model_name, cache_folder
    )
    return HuggingFaceEmbeddings(
        model_name=model_name,
        cache_folder=cache_folder,
        # Normalising the output makes cosine similarity equivalent to
        # inner product, which lines up with FAISS's IndexFlatIP path
        # and gives slightly cleaner top-K rankings on small models.
        encode_kwargs={"normalize_embeddings": True},
    )


def make_embeddings(rag_cfg: RagConfig) -> Any:
    """Return a (cached) ``HuggingFaceEmbeddings`` instance for *rag_cfg*."""

    cache_dir = rag_cfg.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return _make_embeddings_cached(rag_cfg.embedding_model, str(cache_dir))
