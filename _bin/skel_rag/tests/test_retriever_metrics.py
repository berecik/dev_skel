"""Tests for retriever score exposure."""

from __future__ import annotations

from skel_rag.retriever import RetrievedChunk


def test_retrieved_chunk_has_score_field():
    chunk = RetrievedChunk(
        rel_path="app/models.py",
        file="/abs/app/models.py",
        language="python",
        kind="class",
        name="Item",
        start_line=10,
        end_line=30,
        source="class Item: pass",
        score=0.85,
    )
    assert chunk.score == 0.85
    assert chunk.header == "app/models.py:10-30 · class · Item"


def test_retrieved_chunk_score_defaults_to_zero():
    chunk = RetrievedChunk(
        rel_path="x.py",
        file="x.py",
        language="python",
        kind="function",
        name="f",
        start_line=1,
        end_line=5,
        source="def f(): pass",
    )
    assert chunk.score == 0.0
