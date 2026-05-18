"""Phase-2 signatures must validate field names + types and round-trip
through DSPy adapters."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")
from skel_rag.signatures.generate_file import GenerateFile  # noqa: E402


def test_generate_file_signature_has_required_fields():
    fields = GenerateFile.input_fields
    for name in (
        "skeleton_name",
        "target_path",
        "reference_template",
        "retrieved_context",
        "prior_outputs",
        "item_class",
        "item_name",
        "items_plural",
        "service_label",
        "auth_type",
        "backend_extra",
    ):
        assert name in fields, f"missing input field: {name}"
    assert "file_contents" in GenerateFile.output_fields
