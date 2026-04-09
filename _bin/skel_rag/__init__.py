"""Local RAG agent for dev_skel.

This package replaces the "stuff full reference templates into the prompt"
approach previously hard-coded in ``_bin/skel_ai_lib.py``. The pieces are:

* :mod:`skel_rag.config` — :class:`OllamaConfig` + :class:`RagConfig`
  (env-driven).
* :mod:`skel_rag.chunker` — code-aware chunker (tree-sitter for Python,
  Java, TypeScript, Rust + a recursive character splitter fallback).
* :mod:`skel_rag.corpus` — corpus discovery: a skeleton directory or a
  generated wrapper's sibling services.
* :mod:`skel_rag.embedder` — :class:`HuggingFaceEmbeddings` factory with
  on-disk model cache.
* :mod:`skel_rag.vectorstore` — load / build / refresh a local FAISS
  index per corpus.
* :mod:`skel_rag.retriever` — query → top-K chunks with metadata
  filters.
* :mod:`skel_rag.llm` — :class:`langchain_ollama.ChatOllama` factory and
  a small ``chat()`` helper that mimics the old urllib client.
* :mod:`skel_rag.prompts` — assembly helpers for retrieved-context
  blocks and a prompt-aware query builder.
* :mod:`skel_rag.agent` — :class:`RagAgent`, the high-level entry point
  used by the legacy shim and by ``_bin/skel-rag``.
* :mod:`skel_rag.cli` — argparse-based CLI (``index`` / ``search`` /
  ``info`` / ``clean`` / ``generate``).

Heavy LangChain / sentence-transformers / faiss / tree-sitter imports are
deferred to the modules that need them so importing this package never
forces those dependencies on callers (the static ``skel-gen-static`` path
must stay stdlib-only).
"""

from __future__ import annotations

from skel_rag.config import OllamaConfig, RagConfig

__all__ = [
    "OllamaConfig",
    "RagConfig",
]
