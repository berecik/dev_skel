"""DSPy RM adapter for ``skel_rag.retriever.Retriever``.

Why a wrapper instead of using one of DSPy's built-in retrievers: we
already have a tuned tree-sitter chunker plus a FAISS index on disk
for every skeleton. ``dspy.ColBERTv2`` would force us to re-embed and
install ColBERT. Wrapping is one screen of code and keeps the corpus
build path unchanged.

The wrapper is intentionally narrow:

* :meth:`forward` calls the underlying ``Retriever.retrieve`` (which
  returns ``(chunks, stats)``) and lifts each chunk's ``source`` into
  the ``passages`` list of a ``dspy.Prediction``.
* :meth:`from_path` is a convenience factory that builds a
  :class:`RagAgent`, indexes the corpus under *path*, and raises
  ``RuntimeError("retrieval backend unavailable")`` when the embedder
  or FAISS stack is missing — matching the agent's existing "skip
  retrieval and fall back to legacy placeholders" contract.

The agent's own ``generate_targets_with_dspy`` path is *not* wired to
use this wrapper yet. Phases 4 and 6 (integration phase + test/fix
loop) will compose ``SkelRagRM`` inside their DSPy modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import dspy

from skel_rag.config import RagConfig

if TYPE_CHECKING:  # pragma: no cover — typing only
    from skel_rag.retriever import Retriever


class SkelRagRM(dspy.Retrieve):
    """Adapt :class:`skel_rag.retriever.Retriever` to ``dspy.Retrieve``."""

    def __init__(self, retriever: "Retriever", k: int = 5) -> None:
        super().__init__(k=k)
        self._retriever = retriever

    @classmethod
    def from_path(
        cls, path: Path, cfg: Optional[RagConfig] = None
    ) -> "SkelRagRM":
        """Build an RM over the corpus rooted at *path*.

        Raises :class:`RuntimeError` when the retrieval backend is
        unavailable (embeddings or FAISS missing) — callers may catch
        and fall back to the legacy ``{template}`` placeholder flow.
        """

        # Local imports keep the module import-light when the agent
        # stack isn't needed (e.g. when only running the unit tests).
        from skel_rag.agent import RagAgent
        from skel_rag.corpus import corpus_for_skeleton

        rag_cfg = cfg or RagConfig.from_env()
        agent = RagAgent(rag_cfg=rag_cfg)
        retriever = agent.get_retriever(corpus_for_skeleton(Path(path)))
        if retriever is None:
            raise RuntimeError("retrieval backend unavailable")
        return cls(retriever, k=rag_cfg.top_k)

    def forward(
        self, query: str, k: Optional[int] = None
    ) -> dspy.Prediction:
        """Retrieve chunks for *query* and wrap them in a ``dspy.Prediction``.

        ``Retriever.retrieve`` returns ``(chunks, stats)``; we discard
        the stats here because ``dspy.Prediction`` only needs the
        passage list.
        """

        result = self._retriever.retrieve(query, k=k or self.k)
        # The legacy Retriever returns (chunks, stats); tolerate a
        # mock or refactor that returns just chunks.
        if isinstance(result, tuple) and len(result) == 2:
            chunks, _stats = result
        else:
            chunks = result
        passages = [c.source for c in chunks]
        return dspy.Prediction(passages=passages)
