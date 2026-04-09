"""Retrieval over a built FAISS vector store.

The retriever wraps a single :class:`FAISS` instance and exposes a
high-level :meth:`retrieve` method that:

1. Runs ``similarity_search`` for the *full* top-K (the LangChain FAISS
   wrapper does not support pre-filter, so we over-fetch and post-filter).
2. Optionally narrows by language and/or file glob using metadata.
3. Truncates the result to fit ``rag_cfg.max_context_chars``,
   prioritising the highest-ranked chunks.

The retrieved data structure is a plain dataclass so the prompt
assembly step never has to import LangChain.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass
from typing import Any, List, Optional

from skel_rag.config import RagConfig

logger = logging.getLogger("skel_rag.retriever")


@dataclass
class RetrievedChunk:
    """Result of one retrieval hit, decoupled from LangChain types."""

    rel_path: str
    file: str
    language: str
    kind: str
    name: str
    start_line: int
    end_line: int
    source: str

    @property
    def header(self) -> str:
        bits = [f"{self.rel_path}:{self.start_line}-{self.end_line}"]
        if self.kind:
            bits.append(self.kind)
        if self.name:
            bits.append(self.name)
        return " · ".join(bits)


class Retriever:
    """Tiny wrapper around a LangChain ``VectorStore`` instance."""

    def __init__(self, store: Any, rag_cfg: RagConfig) -> None:
        self.store = store
        self.cfg = rag_cfg

    def retrieve(
        self,
        query: str,
        *,
        language: Optional[str] = None,
        file_glob: Optional[str] = None,
        k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """Return up to ``k`` chunks for *query*, language-aware.

        We over-fetch ``2 * top_k`` so post-filtering for language /
        glob still has enough headroom to satisfy ``min_k``. The
        ``max_context_chars`` budget is enforced last so callers don't
        have to track total prompt size themselves.
        """

        target_k = k or self.cfg.top_k
        over_fetch = max(target_k * 2, target_k + self.cfg.min_k)

        try:
            documents = self.store.similarity_search(query, k=over_fetch)
        except Exception as exc:  # noqa: BLE001
            logger.warning("similarity_search failed: %s", exc)
            return []

        chunks: List[RetrievedChunk] = []
        for doc in documents:
            meta = doc.metadata or {}
            chunk = RetrievedChunk(
                rel_path=str(meta.get("rel_path", meta.get("file", ""))),
                file=str(meta.get("file", "")),
                language=str(meta.get("language", "")),
                kind=str(meta.get("kind", "")),
                name=str(meta.get("name", "")),
                start_line=int(meta.get("start_line", 1) or 1),
                end_line=int(meta.get("end_line", 1) or 1),
                source=doc.page_content or "",
            )
            chunks.append(chunk)

        filtered = self._apply_filters(
            chunks, language=language, file_glob=file_glob, target_k=target_k
        )
        return self._budget(filtered, max_chars=self.cfg.max_context_chars)

    # ---- internal helpers -------------------------------------------------

    def _apply_filters(
        self,
        chunks: List[RetrievedChunk],
        *,
        language: Optional[str],
        file_glob: Optional[str],
        target_k: int,
    ) -> List[RetrievedChunk]:
        if not chunks:
            return chunks

        def matches(chunk: RetrievedChunk) -> bool:
            if language and chunk.language != language:
                return False
            if file_glob and not fnmatch.fnmatch(chunk.rel_path, file_glob):
                return False
            return True

        filtered = [c for c in chunks if matches(c)]
        # If the strict filter dropped us below min_k, widen by adding
        # back the highest-ranked rejected chunks (preserves ordering).
        if len(filtered) < self.cfg.min_k:
            seen = set(id(c) for c in filtered)
            for chunk in chunks:
                if id(chunk) in seen:
                    continue
                filtered.append(chunk)
                if len(filtered) >= self.cfg.min_k:
                    break

        return filtered[:target_k]

    @staticmethod
    def _budget(
        chunks: List[RetrievedChunk], *, max_chars: int
    ) -> List[RetrievedChunk]:
        """Drop trailing chunks until the total source length fits."""

        if max_chars <= 0:
            return chunks
        total = 0
        out: List[RetrievedChunk] = []
        for chunk in chunks:
            length = len(chunk.source)
            if total + length > max_chars and out:
                break
            out.append(chunk)
            total += length
        return out
