"""Trainset capture for DSPy optimization.

When ``SKEL_RAG_CAPTURE_TRAINSET=<path>`` is set, every per-target DSPy
generation appends one JSONL record to ``<path>``. The record shape
mirrors the :class:`GenerateFile` signature inputs plus the generated
``file_contents`` and a placeholder ``passed: null`` flag. Operators
backfill the ``passed`` flag manually (or via a post-run script that
diffs the generated tree against a known-good baseline) before piping
the file into :func:`skel_rag.optimize.compile_generate`.

The helper is a silent no-op when the env var is unset so production
runs pay zero cost. Any exception inside the capture path is
swallowed so a misconfigured destination never breaks generation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


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
