"""Phase-7: trainset capture helper.

When ``SKEL_RAG_CAPTURE_TRAINSET=<path>`` is set, every per-target DSPy
generation appends one JSONL record to ``<path>``. With the env var
unset the helper is a silent no-op so production runs pay zero cost.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")

from skel_rag import trainset  # noqa: E402


def test_capture_target_is_noop_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("SKEL_RAG_CAPTURE_TRAINSET", raising=False)
    dest = tmp_path / "trainset.jsonl"

    trainset.capture_target({"foo": "bar"}, "file body")

    assert not dest.exists()


def test_capture_target_appends_jsonl(tmp_path, monkeypatch):
    dest = tmp_path / "trainset.jsonl"
    monkeypatch.setenv("SKEL_RAG_CAPTURE_TRAINSET", str(dest))

    trainset.capture_target({"target_path": "app/api.py"}, "file A")
    trainset.capture_target({"target_path": "app/db.py"}, "file B")

    lines = dest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    rec = json.loads(lines[0])
    assert rec == {
        "inputs": {"target_path": "app/api.py"},
        "file_contents": "file A",
        "passed": None,
    }


def test_capture_target_creates_parent_dir(tmp_path, monkeypatch):
    dest = tmp_path / "nested" / "deep" / "trainset.jsonl"
    monkeypatch.setenv("SKEL_RAG_CAPTURE_TRAINSET", str(dest))

    trainset.capture_target({"k": "v"}, "body")

    assert dest.exists()


def test_capture_target_swallows_errors(tmp_path, monkeypatch):
    """Failures in the capture path must never break the generation
    run — the env var is an observability feature, not a contract."""

    # Create a file where the parent directory must be — mkdir / open
    # will both fail because a regular file already occupies that path.
    blocker = tmp_path / "blocker"
    blocker.write_text("not-a-dir", encoding="utf-8")
    monkeypatch.setenv(
        "SKEL_RAG_CAPTURE_TRAINSET", str(blocker / "child" / "out.jsonl")
    )
    # If this raised, the test would fail.
    trainset.capture_target({"k": "v"}, "body")


def test_load_trainset_filters_unpassed_and_emits_examples(tmp_path):
    dest = tmp_path / "trainset.jsonl"
    records = [
        {"inputs": {"target_path": "a", "item_class": "Order"},
         "file_contents": "ok", "passed": True},
        {"inputs": {"target_path": "b", "item_class": "Order"},
         "file_contents": "bad", "passed": None},
        {"inputs": {"target_path": "c", "item_class": "Order"},
         "file_contents": "fail", "passed": False},
    ]
    dest.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )

    examples = trainset.load_trainset(dest)
    assert len(examples) == 1

    ex = examples[0]
    assert isinstance(ex, dspy.Example)
    assert ex.target_path == "a"
    assert ex.item_class == "Order"
    assert ex.file_contents == "ok"
    # ``with_inputs(*inputs.keys())`` makes ONLY the input keys live.
    assert set(ex.inputs().keys()) == {"target_path", "item_class"}


def test_capture_in_generate_targets_with_dspy_writes_record(tmp_path, monkeypatch):
    """The agent hook calls ``capture_target`` after the predictor
    returns. Verify the env-var-gated path emits one JSONL line per
    successful target without mocking out the full agent — we drive
    the helper directly because that is the seam ``agent.py`` uses."""

    dest = tmp_path / "trainset.jsonl"
    monkeypatch.setenv("SKEL_RAG_CAPTURE_TRAINSET", str(dest))

    gen_inputs = {
        "skeleton_name": "python-fastapi-skel",
        "target_path": "app/api/items.py",
        "item_class": "Order",
    }
    trainset.capture_target(gen_inputs, "<generated file>")

    rec = json.loads(dest.read_text(encoding="utf-8").strip())
    assert rec["inputs"] == gen_inputs
    assert rec["file_contents"] == "<generated file>"
    assert rec["passed"] is None
