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
    2. ``OLLAMA_HOST`` if set. Accepts ``host`` (port defaults to 11434),
       ``host:port``, or ``http(s)://host[:port]``.
    3. Default ``http://localhost:11434``.
    """
    explicit = os.environ.get("OLLAMA_BASE_URL", "").strip()
    if explicit:
        return explicit
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if host:
        if "://" in host:
            return host
        # Bare hostname — append the default Ollama port. Without this
        # `OLLAMA_HOST=paul` resolves to `http://paul` (port 80) and
        # never reaches the daemon.
        if ":" not in host:
            host = f"{host}:11434"
        return f"http://{host}"
    return DEFAULT_OLLAMA_BASE_URL


# --------------------------------------------------------------------------- #
#  SINGLE SOURCE OF TRUTH — Ollama models per pipeline phase
# --------------------------------------------------------------------------- #
#
# Every consumer (skel-gen-ai, ./ai, ./backport, the refactor runtime,
# vendored skel_ai_lib paths) reads its model from this module. Override
# any slot via the matching ``OLLAMA_*_MODEL`` env var; do NOT hard-code
# new defaults elsewhere.
#
# Phase-by-phase rationale (see ``_docs/MODELS.md`` for the full table):
#
#   GEN          — primary code generation. Strong code synthesis +
#                  highest tok/s on the target GPU. Default: qwen3-coder:30b
#                  (~10x faster than qwen3.6:27b on the paul RTX 3090).
#   CREATE_TEST  — test scaffolding. Intentionally DIFFERENT from GEN so
#                  the test author isn't biased by the same model that
#                  wrote the implementation. Default: devstral:24b
#                  (Mistral's code+tests specialist).
#   CHECK_TEST   — review/validate generated tests. A reasoning-strong
#                  model catches missing edge cases better than a code
#                  specialist. Default: qwq:32b (Qwen reasoning model).
#   FIX          — surgical patches when tests fail. Lower temperature,
#                  shorter timeout. Default: qwen2.5-coder:32b (stable,
#                  accurate edits).
#   DOCS         — README, docstrings, comments. The smallest model that
#                  produces clear prose; code reasoning isn't needed.
#                  Default: qwen2.5:7b-instruct.
#
# CONTRACT: CREATE_TEST must differ from GEN (cross-checks the implementation).
# Other slots may overlap by design (FIX shares qwen2.5-coder by default).
DEFAULT_OLLAMA_GEN_MODEL = "qwen3-coder:30b"
DEFAULT_OLLAMA_CREATE_TEST_MODEL = "devstral:latest"
DEFAULT_OLLAMA_CHECK_TEST_MODEL = "qwq:32b"
DEFAULT_OLLAMA_FIX_MODEL = "qwen2.5-coder:32b"
DEFAULT_OLLAMA_DOCS_MODEL = "qwen2.5:7b-instruct"

# Backwards-compat aliases — keep until every consumer imports the new
# names directly. ``OLLAMA_MODEL`` env var still maps to the GEN slot.
DEFAULT_OLLAMA_MODEL = DEFAULT_OLLAMA_GEN_MODEL
DEFAULT_OLLAMA_TEST_MODEL = DEFAULT_OLLAMA_CREATE_TEST_MODEL

# Seconds. Covers cold-load (30-40 s) + generation time. Set to 600
# (10 min) with 3x retry logic so transient Ollama errors are recovered
# within a reasonable window. Override with ``OLLAMA_TIMEOUT``.
#
# Performance env vars (set on the Ollama server):
#   OLLAMA_FLASH_ATTENTION=1    — 1.8-2.3x speedup on Ampere+ GPUs
#   OLLAMA_KV_CACHE_TYPE=q8_0   — 50% less KV cache VRAM
#   OLLAMA_KEEP_ALIVE=24h       — keep model loaded between requests
#
# Per-request env vars (set on the client):
#   OLLAMA_NUM_CTX=32768         — explicit context window size
#   OLLAMA_NUM_PREDICT=4096      — cap output tokens
DEFAULT_TIMEOUT = 600
DEFAULT_TEMPERATURE = 0.2


@dataclass
class OllamaConfig:
    """Connection details for an Ollama server (OpenAI-compatible API).

    Each pipeline phase has its own model slot. Construct via
    :meth:`from_env` so callers stay declarative; switch slots via
    :meth:`for_create_test`, :meth:`for_check_test`, :meth:`for_fix`,
    :meth:`for_docs`.
    """

    # Phase-specific model slots. ``model`` is the GEN slot — kept named
    # ``model`` (rather than ``gen_model``) so the OllamaClient and every
    # callsite that reads ``cfg.model`` keeps working without churn.
    model: str = DEFAULT_OLLAMA_GEN_MODEL
    create_test_model: str = DEFAULT_OLLAMA_CREATE_TEST_MODEL
    check_test_model: str = DEFAULT_OLLAMA_CHECK_TEST_MODEL
    fix_model: str = DEFAULT_OLLAMA_FIX_MODEL
    docs_model: str = DEFAULT_OLLAMA_DOCS_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    temperature: float = DEFAULT_TEMPERATURE

    # Backwards-compat alias kept as a property — pre-refactor callers
    # read ``cfg.test_model`` (the old single test slot) from skel_ai_lib.
    @property
    def test_model(self) -> str:
        return self.create_test_model

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        """Build a config from ``OLLAMA_*`` environment variables.

        Resolution: ``OLLAMA_BASE_URL`` (explicit) → ``OLLAMA_HOST``
        (``host:port``) → default ``localhost:11434``. A trailing
        ``/v1`` is normalised away because the rest of the package
        appends the route segments itself.

        Per-phase env var resolution:

        * ``OLLAMA_GEN_MODEL`` (or legacy ``OLLAMA_MODEL``) → ``model``
        * ``OLLAMA_CREATE_TEST_MODEL`` (or legacy ``OLLAMA_TEST_MODEL``)
          → ``create_test_model``
        * ``OLLAMA_CHECK_TEST_MODEL`` → ``check_test_model``
        * ``OLLAMA_FIX_MODEL`` → ``fix_model``
        * ``OLLAMA_DOCS_MODEL`` → ``docs_model``
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

        # Resolve each model slot, honouring the legacy env-var names so
        # ``OLLAMA_MODEL`` / ``OLLAMA_TEST_MODEL`` still work.
        gen = os.environ.get(
            "OLLAMA_GEN_MODEL",
            os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_GEN_MODEL),
        )
        create_test = os.environ.get(
            "OLLAMA_CREATE_TEST_MODEL",
            os.environ.get("OLLAMA_TEST_MODEL", DEFAULT_OLLAMA_CREATE_TEST_MODEL),
        )
        check_test = os.environ.get(
            "OLLAMA_CHECK_TEST_MODEL", DEFAULT_OLLAMA_CHECK_TEST_MODEL
        )
        fix = os.environ.get("OLLAMA_FIX_MODEL", DEFAULT_OLLAMA_FIX_MODEL)
        docs = os.environ.get("OLLAMA_DOCS_MODEL", DEFAULT_OLLAMA_DOCS_MODEL)

        # Uniqueness contract: CREATE_TEST must differ from BOTH the
        # GEN and FIX models so the test author isn't biased by the
        # model that wrote (or will patch) the implementation. We warn
        # rather than raise so power users can opt into a degraded
        # configuration explicitly via env-var overrides.
        if create_test in (gen, fix):
            import sys as _sys
            print(
                f"[skel_rag.config] WARNING: OLLAMA_CREATE_TEST_MODEL "
                f"({create_test}) overlaps with the "
                f"{'GEN' if create_test == gen else 'FIX'} slot. The "
                f"test author should be a different model from the "
                f"implementation/patch model — see _docs/MODELS.md.",
                file=_sys.stderr,
            )
        # GEN and FIX overlapping is allowed by design (both are code-
        # focused; sharing the model halves cold-load time).

        return cls(
            model=gen,
            create_test_model=create_test,
            check_test_model=check_test,
            fix_model=fix,
            docs_model=docs,
            base_url=base,
            timeout=timeout,
            temperature=temperature,
        )

    def _swap(self, model: str, *, temperature: float | None = None,
              timeout: int | None = None) -> "OllamaConfig":
        """Return a sibling config with a different active model.

        Other slots + base_url are preserved so ``OllamaClient`` stays
        consistent if a caller chains :meth:`for_fix` after :meth:`for_test`.
        """
        return OllamaConfig(
            model=model,
            create_test_model=self.create_test_model,
            check_test_model=self.check_test_model,
            fix_model=self.fix_model,
            docs_model=self.docs_model,
            base_url=self.base_url,
            timeout=timeout if timeout is not None else self.timeout,
            temperature=temperature if temperature is not None else self.temperature,
        )

    def for_fix(self) -> "OllamaConfig":
        """Surgical-patch variant: low temperature, capped at 300 s timeout."""
        return self._swap(self.fix_model, temperature=0.1,
                          timeout=min(self.timeout, 300))

    def for_create_test(self) -> "OllamaConfig":
        """Test-scaffolding variant — must differ from the GEN model."""
        return self._swap(self.create_test_model, temperature=0.2)

    def for_check_test(self) -> "OllamaConfig":
        """Test-validation variant: reasoning-strong model, low temperature."""
        return self._swap(self.check_test_model, temperature=0.1)

    def for_docs(self) -> "OllamaConfig":
        """Docs/comments variant: smallest model, slightly higher temperature."""
        return self._swap(self.docs_model, temperature=0.3)

    # Legacy alias retained for skel_ai_lib's pre-refactor call site.
    def for_test(self) -> "OllamaConfig":
        return self.for_create_test()


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
