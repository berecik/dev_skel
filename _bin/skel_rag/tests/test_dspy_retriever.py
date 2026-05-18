"""Phase-3: a SkelRagRM wraps an existing skel_rag.retriever.Retriever
so DSPy modules can call it like any other ``dspy.Retrieve``.

We test two surfaces:

* A pure-unit test that stubs ``Retriever.retrieve`` and asserts the
  wrapper marshals the result into ``dspy.Prediction(passages=[...])``.
  This always runs as long as ``dspy`` is importable.
* An integration test that drives ``SkelRagRM.from_path`` end-to-end
  against a tiny on-disk corpus. It requires the full embedding +
  FAISS stack, so it is gated on ``faiss`` and
  ``sentence_transformers`` being installed; otherwise it skips
  silently the way every other heavy-deps test in this tree does.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")

from skel_rag.config import RagConfig  # noqa: E402
from skel_rag.dspy_retriever import SkelRagRM  # noqa: E402
from skel_rag.retriever import RetrievedChunk  # noqa: E402


def _make_chunk(source: str, header: str = "a.py:1-2 · function · hello") -> RetrievedChunk:
    """Build a RetrievedChunk that mirrors the real dataclass field layout."""
    return RetrievedChunk(
        rel_path="a.py",
        file="a.py",
        language="python",
        kind="function",
        name="hello",
        start_line=1,
        end_line=2,
        source=source,
        score=0.9,
    )


def test_forward_wraps_retriever_chunks_into_dspy_prediction():
    """SkelRagRM.forward(query) must marshal a list of RetrievedChunk
    into a dspy.Prediction whose .passages is a list of source strings.
    """

    fake_retriever = SimpleNamespace()
    captured: dict[str, object] = {}

    def _retrieve(query: str, *, k: int | None = None, **_kw):  # noqa: ANN001
        captured["query"] = query
        captured["k"] = k
        chunks = [_make_chunk("def hello(): return 'world'")]
        # Real Retriever.retrieve returns (chunks, stats); the wrapper
        # must tolerate that tuple shape.
        return chunks, SimpleNamespace()

    fake_retriever.retrieve = _retrieve

    rm = SkelRagRM(retriever=fake_retriever, k=3)
    pred = rm.forward("hello world")

    assert hasattr(pred, "passages")
    assert pred.passages == ["def hello(): return 'world'"]
    assert captured["query"] == "hello world"
    assert captured["k"] == 3


def test_forward_uses_explicit_k_override():
    """An explicit k argument to forward() overrides the constructor k."""

    fake_retriever = SimpleNamespace()
    captured: dict[str, object] = {}

    def _retrieve(query: str, *, k: int | None = None, **_kw):  # noqa: ANN001
        captured["k"] = k
        return [_make_chunk("snippet")], SimpleNamespace()

    fake_retriever.retrieve = _retrieve

    rm = SkelRagRM(retriever=fake_retriever, k=3)
    pred = rm.forward("q", k=7)

    assert pred.passages == ["snippet"]
    assert captured["k"] == 7


def test_from_path_raises_when_retriever_unavailable(tmp_path):
    """SkelRagRM.from_path must raise RuntimeError when the embedding/FAISS
    backend is unavailable (RagAgent.get_retriever returns None)."""

    (tmp_path / "a.py").write_text("def hello():\n    return 'world'\n")

    # RagAgent is imported lazily inside from_path(), so patch it at the
    # module that defines it. patch.object on the class' get_retriever
    # method gives us a stable target regardless of import timing.
    from skel_rag.agent import RagAgent as _RagAgent

    with patch.object(_RagAgent, "get_retriever", return_value=None):
        with pytest.raises(RuntimeError, match="retrieval backend unavailable"):
            SkelRagRM.from_path(tmp_path, RagConfig.from_env())


# --------------------------------------------------------------------------- #
#  Integration: real FAISS + embeddings round-trip. Skips when deps missing.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("SKEL_RAG_RUN_REAL_FAISS_TEST") != "1",
    reason=(
        "real FAISS + embedder round-trip is gated behind "
        "SKEL_RAG_RUN_REAL_FAISS_TEST=1 because the HF nomic embedder "
        "segfaults under Python 3.14 on some hosts"
    ),
)
def test_from_path_real_round_trip(tmp_path):
    """End-to-end: index a tiny on-disk corpus, retrieve through SkelRagRM,
    assert the matching passage comes back. Gated on faiss + ST install
    AND on an opt-in env var (SKEL_RAG_RUN_REAL_FAISS_TEST=1) so a
    flaky embedder install never crashes the pytest interpreter in CI.
    """

    pytest.importorskip("faiss")
    pytest.importorskip("sentence_transformers")

    (tmp_path / "a.py").write_text("def hello():\n    return 'world'\n")
    cfg = RagConfig.from_env()
    try:
        rm = SkelRagRM.from_path(tmp_path, cfg)
    except RuntimeError as exc:  # pragma: no cover — env-dependent
        pytest.skip(f"retrieval backend unavailable: {exc}")

    pred = rm("hello world")
    assert hasattr(pred, "passages")
    assert any("hello" in p for p in pred.passages)
