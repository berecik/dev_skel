"""Phase-5: CHECK_TEST review through a composed DSPy program.

The :class:`CheckedGenerateProgram` wraps the per-target
:class:`GenerateFile` predictor with a :class:`ReviewGeneratedFile`
predictor. When the reviewer returns ``verdict == "FAIL"`` the program
falls back to a one-shot manual retry (because :func:`dspy.Suggest`
isn't available in our installed DSPy 3.2.x) and returns the second
prediction. When the reviewer returns ``verdict == "OK"`` the program
returns the original prediction unchanged with no retry.

The legacy ``RagAgent._maybe_check_target`` keeps its current
behaviour — Phase 5 only adds a parallel DSPy path on the
``SKEL_RAG_USE_DSPY=1`` branch.
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

from skel_rag.signatures.check_test import ReviewGeneratedFile  # noqa: E402


def test_review_generated_file_signature_has_required_fields() -> None:
    fields = ReviewGeneratedFile.input_fields
    for name in ("generated_file", "sibling_files", "contract"):
        assert name in fields, f"missing input field: {name}"
    for name in ("verdict", "reason"):
        assert name in ReviewGeneratedFile.output_fields, (
            f"missing output field: {name}"
        )


class _StubPredictor:
    """Callable double for ``dspy.Predict(...)``.

    ``side_effect`` is a list of ``SimpleNamespace`` outputs. Each call
    pops the next one and records its kwargs.
    """

    def __init__(self, outputs: list[SimpleNamespace]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def __call__(self, **kwargs):  # noqa: D401 — DSPy call surface
        self.calls.append(kwargs)
        if not self.outputs:
            raise AssertionError("Predictor called more times than expected")
        return self.outputs.pop(0)


def _make_program(generate_outputs, review_outputs):
    """Return ``(program, generate_stub, review_stub)`` with stubs in
    place for both inner predictors, so tests can introspect call counts.
    """

    from skel_rag.programs.generate_with_check import CheckedGenerateProgram

    generate_stub = _StubPredictor(generate_outputs)
    review_stub = _StubPredictor(review_outputs)

    def _fake_predict(signature):
        # The program constructs two Predict() instances back to back:
        # first for GenerateFile, then for ReviewGeneratedFile.
        # We dispatch on the signature class name.
        name = getattr(signature, "__name__", "")
        if name == "GenerateFile":
            return generate_stub
        if name == "ReviewGeneratedFile":
            return review_stub
        raise AssertionError(f"unexpected signature: {name!r}")

    with patch("dspy.Predict", side_effect=_fake_predict):
        program = CheckedGenerateProgram()
    return program, generate_stub, review_stub


_GEN_KWARGS = dict(
    skeleton_name="python-fastapi-skel",
    target_path="app/models/order.py",
    reference_template="# example",
    retrieved_context="",
    prior_outputs="",
    item_class="Order",
    item_name="order",
    items_plural="orders",
    service_label="Order Service",
    auth_type="jwt",
    backend_extra="",
)


def test_happy_path_returns_first_prediction_without_retry() -> None:
    """Verdict OK → original prediction returned, generate called once."""

    good_pred = SimpleNamespace(file_contents="class Order: pass\n")
    program, generate_stub, review_stub = _make_program(
        generate_outputs=[good_pred],
        review_outputs=[SimpleNamespace(verdict="OK", reason="")],
    )

    result = program.forward(
        sibling_files="",
        contract="",
        **_GEN_KWARGS,
    )

    assert result is good_pred
    assert len(generate_stub.calls) == 1
    assert len(review_stub.calls) == 1


def test_fail_verdict_triggers_one_shot_retry() -> None:
    """Verdict FAIL → generate called twice; the second prediction is
    returned. Mirrors the legacy ``_maybe_check_target`` "regenerate
    once" behaviour.
    """

    bad_pred = SimpleNamespace(file_contents="bad import\n")
    fixed_pred = SimpleNamespace(file_contents="from foo import bar\n")
    program, generate_stub, review_stub = _make_program(
        generate_outputs=[bad_pred, fixed_pred],
        review_outputs=[SimpleNamespace(verdict="FAIL", reason="missing module")],
    )

    result = program.forward(
        sibling_files="(sibling files)",
        contract="",
        **_GEN_KWARGS,
    )

    # The fallback retry returns the *second* generation.
    assert result is fixed_pred
    assert len(generate_stub.calls) == 2, (
        "expected one retry after FAIL verdict; got "
        f"{len(generate_stub.calls)} generate calls"
    )
    # The reviewer is invoked once on the original output. The retry
    # hint is appended to one of the inputs of the second generate call
    # so the model sees the critique.
    assert len(review_stub.calls) == 1
    # The reason must be threaded into the retry call somewhere so the
    # model can act on it. We accept any field carrying the reason.
    second_call_inputs = " ".join(
        v for v in generate_stub.calls[1].values() if isinstance(v, str)
    )
    assert "missing module" in second_call_inputs


# --------------------------------------------------------------------------- #
#  Gated live-Ollama test: only runs when SKEL_PHASE5_LIVE_OLLAMA=1.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("SKEL_PHASE5_LIVE_OLLAMA") != "1",
    reason=(
        "live Ollama check test is gated behind "
        "SKEL_PHASE5_LIVE_OLLAMA=1 so normal test runs stay fast"
    ),
)
def test_checked_generate_program_live_ollama_smoke() -> None:
    """End-to-end against real Ollama: ask for one trivial file, run
    through the reviewer. Assert only that non-empty file_contents
    comes back — content quality is validated by the pizzeria suite.
    """

    from skel_rag.config import OllamaConfig
    from skel_rag.dspy_lm import make_lm
    from skel_rag.programs.generate_with_check import CheckedGenerateProgram

    cfg = OllamaConfig.from_env()
    lm = make_lm(cfg)

    with dspy.context(lm=lm):
        program = CheckedGenerateProgram()
        pred = program(
            sibling_files="",
            contract="",
            skeleton_name="python-fastapi-skel",
            target_path="hello.py",
            reference_template="print('example')\n",
            retrieved_context="",
            prior_outputs="",
            item_class="Greeting",
            item_name="greeting",
            items_plural="greetings",
            service_label="Greeting Service",
            auth_type="jwt",
            backend_extra="",
        )

    assert hasattr(pred, "file_contents")
    assert isinstance(pred.file_contents, str)
    assert pred.file_contents.strip()
