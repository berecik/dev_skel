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


# --------------------------------------------------------------------- #
#  Fix-loop trainset capture (Phase 7+ addition)
# --------------------------------------------------------------------- #


def test_capture_fix_attempt_is_noop_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("SKEL_RAG_CAPTURE_FIX_TRAINSET", raising=False)
    monkeypatch.delenv("SKEL_RAG_CAPTURE_TRAINSET", raising=False)

    trainset.capture_fix_attempt(
        file_path="app/foo.py",
        current_contents="old",
        test_output="boom",
        sibling_context="",
        fixed_contents="new",
        post_test_output="1 passed in 1.0s",
    )
    # Nothing should have been created; we don't even know what path
    # would have been used.
    assert list(tmp_path.iterdir()) == []


def test_capture_fix_attempt_writes_record(tmp_path, monkeypatch):
    dest = tmp_path / "fix.jsonl"
    monkeypatch.setenv("SKEL_RAG_CAPTURE_FIX_TRAINSET", str(dest))

    trainset.capture_fix_attempt(
        file_path="app/foo.py",
        current_contents="def foo(): return 0",
        test_output="AssertionError",
        sibling_context="from app.bar import baz",
        fixed_contents="def foo(): return 1",
        post_test_output="1 passed in 1.0s",
    )

    rec = json.loads(dest.read_text(encoding="utf-8").strip())
    assert rec["inputs"]["file_path"] == "app/foo.py"
    assert rec["inputs"]["sibling_context"] == "from app.bar import baz"
    assert rec["fixed_contents"] == "def foo(): return 1"
    assert rec["post_test_output"] == "1 passed in 1.0s"


def test_capture_fix_attempt_falls_back_to_generic_var(tmp_path, monkeypatch):
    """A single ``SKEL_RAG_CAPTURE_TRAINSET`` flip lets a maintainer
    capture both phases for an A/B without managing two env vars.
    The fallback rewrites the suffix to ``.fix.jsonl`` so the gen and
    fix records stay in separate files."""

    base = tmp_path / "out.jsonl"
    monkeypatch.delenv("SKEL_RAG_CAPTURE_FIX_TRAINSET", raising=False)
    monkeypatch.setenv("SKEL_RAG_CAPTURE_TRAINSET", str(base))

    trainset.capture_fix_attempt(
        file_path="x.py",
        current_contents="a",
        test_output="b",
        sibling_context="c",
        fixed_contents="d",
        post_test_output="1 passed in 0.1s",
    )

    expected = tmp_path / "out.fix.jsonl"
    assert expected.is_file()
    assert not base.exists(), "fix capture must not write to the gen file"


def test_load_fix_trainset_filters_by_pass_ratio(tmp_path):
    dest = tmp_path / "fix.jsonl"
    records = [
        # All green → ratio 1.0, kept.
        {
            "inputs": {
                "file_path": "a.py", "current_contents": "x",
                "test_output": "y", "sibling_context": "",
            },
            "fixed_contents": "good",
            "post_test_output": "1 passed in 0.1s",
        },
        # 56/(56+5) ≈ 0.918 → kept (above default 0.5).
        {
            "inputs": {
                "file_path": "b.py", "current_contents": "x",
                "test_output": "y", "sibling_context": "",
            },
            "fixed_contents": "mostly-good",
            "post_test_output": "5 failed, 56 passed in 1.0s",
        },
        # 1/(1+10) ≈ 0.09 → dropped at default threshold.
        {
            "inputs": {
                "file_path": "c.py", "current_contents": "x",
                "test_output": "y", "sibling_context": "",
            },
            "fixed_contents": "bad",
            "post_test_output": "10 failed, 1 passed in 1.0s",
        },
        # Unparseable post output → ratio 0.0, dropped.
        {
            "inputs": {
                "file_path": "d.py", "current_contents": "x",
                "test_output": "y", "sibling_context": "",
            },
            "fixed_contents": "infra-failed",
            "post_test_output": "kaboom",
        },
    ]
    dest.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )

    examples = trainset.load_fix_trainset(dest)
    paths = sorted(ex.file_path for ex in examples)
    assert paths == ["a.py", "b.py"]
    # Each Example must carry exactly the FixFailingFile signature
    # inputs as the live keys.
    assert set(examples[0].inputs().keys()) == {
        "file_path", "current_contents", "test_output", "sibling_context",
    }


def test_load_fix_trainset_min_pass_ratio_override(tmp_path):
    dest = tmp_path / "fix.jsonl"
    record = {
        "inputs": {
            "file_path": "c.py", "current_contents": "x",
            "test_output": "y", "sibling_context": "",
        },
        "fixed_contents": "marginal",
        # 1 / (1 + 10) ≈ 0.09 — only kept when threshold drops to 0.0.
        "post_test_output": "10 failed, 1 passed in 1.0s",
    }
    dest.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert len(trainset.load_fix_trainset(dest)) == 0
    assert len(trainset.load_fix_trainset(dest, min_pass_ratio=0.0)) == 1
