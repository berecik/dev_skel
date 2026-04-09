"""Local FAISS vector store helpers.

The store is **per corpus**: a skeleton's index lives at
``_skels/<name>/.skel_rag_index/`` and a generated wrapper's ephemeral
index lives at ``<wrapper>/.skel_rag_index/``. Each store is a directory
containing:

* ``vectors.faiss`` / ``index.pkl`` — written by LangChain's
  ``FAISS.save_local()``.
* ``manifest.json`` — `{rel_path: {mtime, size, sha}}` used to decide
  whether the cached index is still valid.

The whole module imports LangChain lazily; unit tests that only chunk
or walk the corpus do not need ``langchain-community`` installed.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, List, Optional

from skel_rag.chunker import CodeChunker, chunks_to_documents
from skel_rag.config import RagConfig
from skel_rag.corpus import Corpus, compute_manifest, manifests_match

logger = logging.getLogger("skel_rag.vectorstore")


class VectorStoreError(RuntimeError):
    """Raised when the FAISS backend cannot be loaded or built."""


# --------------------------------------------------------------------------- #
#  Path helpers
# --------------------------------------------------------------------------- #


def index_dir(corpus: Corpus, rag_cfg: RagConfig) -> Path:
    return corpus.root / rag_cfg.index_dirname


def _manifest_path(index_root: Path) -> Path:
    return index_root / "manifest.json"


def _is_index_present(index_root: Path) -> bool:
    return (index_root / "index.faiss").is_file() and (
        index_root / "index.pkl"
    ).is_file()


# --------------------------------------------------------------------------- #
#  Build / load
# --------------------------------------------------------------------------- #


def load_or_build(
    corpus: Corpus,
    rag_cfg: RagConfig,
    embeddings: Any,
    *,
    rebuild: bool = False,
    persist: bool = True,
) -> Any:
    """Return a FAISS vector store for *corpus*, building it if needed.

    Args:
        corpus:    The :class:`Corpus` to index.
        rag_cfg:   Active :class:`RagConfig`.
        embeddings: A LangChain embeddings instance (typically returned
                    by :func:`skel_rag.embedder.make_embeddings`).
        rebuild:   When ``True``, ignore any cached index and rebuild
                   from scratch.
        persist:   When ``True``, persist the resulting index to disk.
                   The wrapper integration phase passes ``persist=False``
                   so we don't litter generated wrappers with .skel_rag_index/
                   directories.
    """

    try:
        from langchain_community.vectorstores import FAISS  # type: ignore
    except ImportError as exc:
        raise VectorStoreError(
            "langchain-community is not installed. Run "
            "`make install-rag-deps` to enable the RAG agent."
        ) from exc

    target = index_dir(corpus, rag_cfg)
    current_manifest = compute_manifest(corpus)

    if not rebuild and persist and _is_index_present(target):
        cached = _read_manifest(target)
        if cached is not None and manifests_match(cached, current_manifest):
            logger.debug("reusing cached FAISS index at %s", target)
            try:
                return FAISS.load_local(
                    str(target),
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
            except Exception as exc:  # noqa: BLE001 — fall back to rebuild
                logger.warning(
                    "could not load cached index at %s (%s); rebuilding",
                    target,
                    exc,
                )

    logger.info(
        "building FAISS index for corpus %s (%d files)",
        corpus.id,
        len(corpus.files),
    )

    documents = _chunk_corpus(corpus, rag_cfg)
    if not documents:
        raise VectorStoreError(
            f"corpus {corpus.id!r} produced no chunks — nothing to index"
        )

    store = FAISS.from_documents(documents, embeddings)

    if persist:
        target.mkdir(parents=True, exist_ok=True)
        store.save_local(str(target))
        _write_manifest(target, current_manifest)
        logger.info("persisted FAISS index to %s", target)

    return store


def clean(corpus: Corpus, rag_cfg: RagConfig) -> bool:
    """Remove the persisted index directory for *corpus*. Returns True
    when something was removed."""

    target = index_dir(corpus, rag_cfg)
    if not target.exists():
        return False
    shutil.rmtree(target, ignore_errors=True)
    return True


def info(corpus: Corpus, rag_cfg: RagConfig) -> dict:
    """Return a small dict describing the on-disk index for *corpus*."""

    target = index_dir(corpus, rag_cfg)
    if not _is_index_present(target):
        return {
            "corpus_id": corpus.id,
            "root": str(corpus.root),
            "index_present": False,
            "files": len(corpus.files),
        }
    cached = _read_manifest(target) or {}
    return {
        "corpus_id": corpus.id,
        "root": str(corpus.root),
        "index_present": True,
        "files": len(corpus.files),
        "manifest_entries": len(cached),
        "index_dir": str(target),
    }


# --------------------------------------------------------------------------- #
#  Internal
# --------------------------------------------------------------------------- #


def _chunk_corpus(corpus: Corpus, rag_cfg: RagConfig) -> List[Any]:
    chunker = CodeChunker(rag_cfg)
    raw_chunks = []
    for path in corpus.files:
        raw_chunks.extend(chunker.chunk_file(path, corpus_root=corpus.root))
    return chunks_to_documents(raw_chunks, corpus_id=corpus.id)


def _read_manifest(index_root: Path) -> Optional[dict]:
    path = _manifest_path(index_root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_manifest(index_root: Path, manifest: dict) -> None:
    path = _manifest_path(index_root)
    try:
        path.write_text(
            json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("could not write manifest %s: %s", path, exc)
