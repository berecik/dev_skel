"""Trainset capture for DSPy optimization.

Two capture entry points and one loader live here:

* :func:`capture_target` — for the per-target generation phase.
  Appends one JSONL record per file the AI writes, with placeholder
  ``passed: null`` until a downstream post-pass marks it.
* :func:`capture_fix_attempt` — for the test/fix loop. Appends one
  record per ``(file, before, after, post_test_summary)`` tuple. The
  ``post_test_summary`` is the pytest output AFTER the fix was
  written and the test command was re-run, so the loader can
  compute ``metric_pass_ratio`` directly with no manual annotation.
* :func:`load_trainset` — loads :class:`GenerateFile`-shaped
  records (legacy).
* :func:`load_fix_trainset` — loads :class:`FixFailingFile`-shaped
  records and computes the ``passed`` flag + ``output`` on the fly.

Both capture helpers are silent no-ops when
``SKEL_RAG_CAPTURE_TRAINSET`` (or the fix-specific
``SKEL_RAG_CAPTURE_FIX_TRAINSET``) is unset, so production pays
zero cost. Any exception inside a capture is swallowed so a
misconfigured destination never breaks generation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def capture_target(inputs: Dict[str, Any], file_contents: str) -> None:
    """Append one ``(inputs, output)`` record to the trainset file.

    Silent no-op when ``SKEL_RAG_CAPTURE_TRAINSET`` is unset.
    """

    dest = os.environ.get("SKEL_RAG_CAPTURE_TRAINSET", "").strip()
    if not dest:
        return
    try:
        p = Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "inputs": inputs,
            "file_contents": file_contents,
            "passed": None,
        }
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        # Never break the generation path.
        pass


def capture_fix_attempt(
    *,
    file_path: str,
    current_contents: str,
    test_output: str,
    sibling_context: str,
    fixed_contents: str,
    post_test_output: str,
) -> None:
    """Record one fix attempt with its post-write test output.

    Honours the dedicated ``SKEL_RAG_CAPTURE_FIX_TRAINSET`` env var so
    fix demos can be kept in a separate file from per-target gen
    demos (they share schema otherwise but have different optimization
    budgets).

    Falls back to ``SKEL_RAG_CAPTURE_TRAINSET`` when the dedicated var
    is unset and the generic one is set with a ``.fix.jsonl`` suffix,
    so a single env-var flip captures both phases for a one-off A/B.
    """

    dest = os.environ.get("SKEL_RAG_CAPTURE_FIX_TRAINSET", "").strip()
    if not dest:
        generic = os.environ.get("SKEL_RAG_CAPTURE_TRAINSET", "").strip()
        if generic:
            dest = generic.removesuffix(".jsonl") + ".fix.jsonl"
    if not dest:
        return
    try:
        p = Path(dest)
        p.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "inputs": {
                "file_path": file_path,
                "current_contents": current_contents,
                "test_output": test_output,
                "sibling_context": sibling_context,
            },
            "fixed_contents": fixed_contents,
            "post_test_output": post_test_output,
        }
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        # Never break the fix path.
        pass


def load_trainset(path: Path) -> list:
    """Load a JSONL trainset into a list of ``dspy.Example`` objects.

    Only records where ``passed=True`` are returned — the optimizer
    trains on confirmed successes.
    """

    import dspy

    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not rec.get("passed"):
            continue
        inputs = rec["inputs"]
        ex = dspy.Example(
            **inputs,
            file_contents=rec["file_contents"],
        ).with_inputs(*inputs.keys())
        out.append(ex)
    return out


def load_fix_trainset(
    path: Path, *, min_pass_ratio: float = 0.5,
) -> List[Any]:
    """Load :func:`capture_fix_attempt` records as ``dspy.Example`` objects.

    Each returned Example carries:

    * ``file_path``, ``current_contents``, ``test_output``,
      ``sibling_context`` — the four inputs to :class:`FixFailingFile`.
    * ``fixed_contents`` — the LM output, kept as a labeled target so
      ``BootstrapFewShot`` can use it as a few-shot exemplar.
    * ``passed`` and ``output`` — computed from the recorded
      ``post_test_output``. These let :func:`metric_pass_ratio`
      score the example without re-running pytest.

    Records whose ``post_test_output`` parses to a pass_ratio below
    *min_pass_ratio* are dropped (defaults to 0.5 — keep fixes that
    moved tests at least halfway green). Set to 0.0 to keep
    everything for a heavier MIPROv2 run.
    """

    import dspy

    from skel_rag.programs.metrics import metric_pass_ratio, parse_pytest_summary

    out: List[Any] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        inputs = rec.get("inputs") or {}
        if not inputs:
            continue
        post_output = rec.get("post_test_output", "") or ""
        summary = parse_pytest_summary(post_output)
        passed = summary.all_green
        # Build a synthetic Prediction so the same metric is used here
        # as during a live run — keeps trainset filtering aligned with
        # the optimizer's reward.
        pred_like = type("P", (), {"passed": passed, "output": post_output})()
        ratio = metric_pass_ratio(None, pred_like)
        if ratio < min_pass_ratio:
            continue
        ex = dspy.Example(
            **inputs,
            fixed_contents=rec.get("fixed_contents", ""),
        ).with_inputs(*inputs.keys())
        out.append(ex)
    return out
