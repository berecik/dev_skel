"""Configuration objects for the RAG agent.

Two configs live here:

* :class:`OllamaConfig` — connection details for the local Ollama server.
  Moved verbatim from ``_bin/skel_ai_lib.py`` so the shim can re-export
  it without behavioural drift.
* :class:`RagConfig` — knobs for the chunker / embedder / vector store /
  retriever. Every field has a sensible default and a corresponding
  ``SKEL_RAG_*`` environment variable so power users can tune behaviour
  without editing code.

Both classes are stdlib-only on purpose: importing this module must not
pull in tree-sitter, sentence-transformers, faiss, or LangChain.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# --------------------------------------------------------------------------- #
#  Ollama connection
# --------------------------------------------------------------------------- #


DEFAULT_OLLAMA_HOST = "localhost:11434"
DEFAULT_OLLAMA_BASE_URL = f"http://{DEFAULT_OLLAMA_HOST}"


def _resolve_base_url() -> str:
    """Derive the Ollama base URL from environment variables.

    Resolution order:
    1. ``OLLAMA_BASE_URL`` if set explicitly (full URL).
    2. ``OLLAMA_HOST`` if set (``host:port`` → ``http://host:port``).
    3. Default ``http://localhost:11434``.
    """
    explicit = os.environ.get("OLLAMA_BASE_URL", "").strip()
    if explicit:
        return explicit
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if host:
        return f"http://{host}" if "://" not in host else host
    return DEFAULT_OLLAMA_BASE_URL


DEFAULT_OLLAMA_MODEL = "qwen3.6:27b"
DEFAULT_OLLAMA_FIX_MODEL = "qwen2.5-coder:32b"
DEFAULT_OLLAMA_TEST_MODEL = "qwen2.5-coder:32b"
# Seconds. Local Ollama can be slow on big models. The default is sized for
# ~30B-class instruction models like ``gemma4:31b`` — a single completion
# can include a 30-40 s cold-load on the first call plus several minutes
# of generation on long files. Override with ``OLLAMA_TIMEOUT`` in the
# environment when running on faster hardware or against a smaller model.
DEFAULT_TIMEOUT = 1800
DEFAULT_TEMPERATURE = 0.2


@dataclass
class OllamaConfig:
    """Connection details for an Ollama server (OpenAI-compatible API)."""

    model: str = DEFAULT_OLLAMA_MODEL
    fix_model: str = DEFAULT_OLLAMA_FIX_MODEL
    test_model: str = DEFAULT_OLLAMA_TEST_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    temperature: float = DEFAULT_TEMPERATURE

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        """Build a config from ``OLLAMA_*`` environment variables.

        Resolution: ``OLLAMA_BASE_URL`` (explicit) → ``OLLAMA_HOST``
        (``host:port``) → default ``localhost:11434``. A trailing
        ``/v1`` is normalised away because the rest of the package
        appends the route segments itself.
        """

        base = _resolve_base_url()
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        if base.endswith("/"):
            base = base.rstrip("/")
        try:
            timeout = int(os.environ.get("OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT)))
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        try:
            temperature = float(
                os.environ.get("OLLAMA_TEMPERATURE", str(DEFAULT_TEMPERATURE))
            )
        except ValueError:
            temperature = DEFAULT_TEMPERATURE
        return cls(
            model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            fix_model=os.environ.get(
                "OLLAMA_FIX_MODEL", DEFAULT_OLLAMA_FIX_MODEL
            ),
            test_model=os.environ.get(
                "OLLAMA_TEST_MODEL", DEFAULT_OLLAMA_TEST_MODEL
            ),
            base_url=base,
            timeout=timeout,
            temperature=temperature,
        )

    def for_fix(self) -> "OllamaConfig":
        """Return a config variant using the fix model.

        Lower temperature (0.1) for deterministic patches, shorter
        timeout (300s) since fixes should be fast.
        """
        return OllamaConfig(
            model=self.fix_model,
            fix_model=self.fix_model,
            test_model=self.test_model,
            base_url=self.base_url,
            timeout=min(self.timeout, 300),
            temperature=0.1,
        )

    def for_test(self) -> "OllamaConfig":
        """Return a config variant using the test generation model.

        devstral produces better test structure than code-focused models.
        """
        return OllamaConfig(
            model=self.test_model,
            fix_model=self.fix_model,
            test_model=self.test_model,
            base_url=self.base_url,
            timeout=self.timeout,
            temperature=0.2,
        )


# --------------------------------------------------------------------------- #
#  RAG knobs
# --------------------------------------------------------------------------- #


# Small, fast, normalisable embedding model. ~130 MB on disk, runs on CPU,
# strong on code/text. Override with ``SKEL_RAG_EMBEDDING_MODEL`` if you
# want to swap in a heavier model (e.g. ``BAAI/bge-base-en-v1.5``) or the
# claude-context-local default (``google/embeddinggemma-300m``).
DEFAULT_EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
DEFAULT_INDEX_DIRNAME = ".skel_rag_index"
DEFAULT_TOP_K = 8
DEFAULT_MIN_K = 3
DEFAULT_MAX_CONTEXT_CHARS = 12000
DEFAULT_CHUNK_MAX_CHARS = 6000
DEFAULT_FALLBACK_CHUNK_SIZE = 1500
DEFAULT_FALLBACK_CHUNK_OVERLAP = 150


def _default_cache_dir() -> Path:
    """Return ``~/.cache/dev_skel/embeddings`` as a :class:`Path`."""

    return Path(
        os.environ.get(
            "SKEL_RAG_CACHE_DIR",
            str(Path.home() / ".cache" / "dev_skel" / "embeddings"),
        )
    ).expanduser()


@dataclass
class RagConfig:
    """Knobs for the chunker / embedder / vector store / retriever.

    All fields have a corresponding ``SKEL_RAG_*`` env var. Construct via
    :meth:`from_env` so callers stay declarative.
    """

    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    index_dirname: str = DEFAULT_INDEX_DIRNAME
    cache_dir: Path = field(default_factory=_default_cache_dir)
    top_k: int = DEFAULT_TOP_K
    min_k: int = DEFAULT_MIN_K
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS
    fallback_chunk_size: int = DEFAULT_FALLBACK_CHUNK_SIZE
    fallback_chunk_overlap: int = DEFAULT_FALLBACK_CHUNK_OVERLAP
    verbose: int = 0

    @classmethod
    def from_env(cls) -> "RagConfig":
        def _int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)))
            except ValueError:
                return default

        return cls(
            embedding_model=os.environ.get(
                "SKEL_RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
            ),
            index_dirname=os.environ.get(
                "SKEL_RAG_INDEX_DIRNAME", DEFAULT_INDEX_DIRNAME
            ),
            cache_dir=_default_cache_dir(),
            top_k=_int("SKEL_RAG_TOP_K", DEFAULT_TOP_K),
            min_k=_int("SKEL_RAG_MIN_K", DEFAULT_MIN_K),
            max_context_chars=_int(
                "SKEL_RAG_MAX_CONTEXT_CHARS", DEFAULT_MAX_CONTEXT_CHARS
            ),
            chunk_max_chars=_int(
                "SKEL_RAG_CHUNK_MAX_CHARS", DEFAULT_CHUNK_MAX_CHARS
            ),
            fallback_chunk_size=_int(
                "SKEL_RAG_FALLBACK_CHUNK_SIZE", DEFAULT_FALLBACK_CHUNK_SIZE
            ),
            fallback_chunk_overlap=_int(
                "SKEL_RAG_FALLBACK_CHUNK_OVERLAP", DEFAULT_FALLBACK_CHUNK_OVERLAP
            ),
            verbose=_int("SKEL_AI_VERBOSE", 0),
        )
