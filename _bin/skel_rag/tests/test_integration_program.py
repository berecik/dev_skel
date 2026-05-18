"""Phase-4: IntegrationProgram wraps dspy.ChainOfThought(IntegrateService)
so the wrapper-level integration phase can run as a composed DSPy Module.

We test three surfaces:

* A pure-unit test that monkey-patches ``dspy.ChainOfThought`` to return
  a stub predictor, then asserts ``IntegrationProgram()(...)`` returns the
  stub's ``dspy.Prediction``. Always runs as long as ``dspy`` is importable.
* The signature itself exposes the expected input/output fields.
* A gated live-Ollama smoke that only fires when ``SKEL_PHASE4_LIVE_OLLAMA=1``
  so normal test runs stay fast and Ollama-free.
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

from skel_rag.signatures.integrate import IntegrateService  # noqa: E402


def test_integrate_service_signature_has_required_fields():
    fields = IntegrateService.input_fields
    for name in (
        "target_path",
        "retrieved_siblings",
        "item_class",
        "service_label",
        "integration_extra",
    ):
        assert name in fields, f"missing input field: {name}"
    assert "file_contents" in IntegrateService.output_fields


def test_integration_program_delegates_to_chain_of_thought():
    """IntegrationProgram() should construct a ChainOfThought(IntegrateService)
    and forward kwargs to it, returning the predictor's Prediction.
    """

    from skel_rag.programs.integration import IntegrationProgram

    captured: dict[str, object] = {}
    expected = dspy.Prediction(file_contents="print('hi')\n")

    def _fake_predictor(**kwargs):
        captured.update(kwargs)
        return expected

    with patch("dspy.ChainOfThought", return_value=_fake_predictor):
        program = IntegrationProgram()
        result = program(
            target_path="app/integration_test.py",
            retrieved_siblings="(sibling files...)",
            item_class="Order",
            service_label="Order Service",
            integration_extra="use psycopg2",
        )

    assert result is expected
    assert captured["target_path"] == "app/integration_test.py"
    assert captured["retrieved_siblings"] == "(sibling files...)"
    assert captured["item_class"] == "Order"
    assert captured["service_label"] == "Order Service"
    assert captured["integration_extra"] == "use psycopg2"


def test_integration_program_default_integration_extra():
    """integration_extra defaults to empty string."""

    from skel_rag.programs.integration import IntegrationProgram

    captured: dict[str, object] = {}

    def _fake_predictor(**kwargs):
        captured.update(kwargs)
        return dspy.Prediction(file_contents="")

    with patch("dspy.ChainOfThought", return_value=_fake_predictor):
        program = IntegrationProgram()
        program(
            target_path="t.py",
            retrieved_siblings="",
            item_class="X",
            service_label="X Service",
        )

    assert captured["integration_extra"] == ""


# --------------------------------------------------------------------------- #
#  Gated live-Ollama test: only runs when SKEL_PHASE4_LIVE_OLLAMA=1.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("SKEL_PHASE4_LIVE_OLLAMA") != "1",
    reason=(
        "live Ollama integration smoke is gated behind "
        "SKEL_PHASE4_LIVE_OLLAMA=1 so normal test runs stay fast"
    ),
)
def test_integration_program_live_ollama_smoke():
    """End-to-end: configure DSPy with the project's OllamaConfig and run
    IntegrationProgram against a trivial fixture. Asserts only that a
    non-empty file_contents string comes back — content quality is
    validated by make test-shared-db-python in Phase 8.
    """

    from skel_rag.config import OllamaConfig
    from skel_rag.dspy_lm import make_lm
    from skel_rag.programs.integration import IntegrationProgram

    cfg = OllamaConfig.from_env()
    lm = make_lm(cfg)

    with dspy.context(lm=lm):
        program = IntegrationProgram()
        pred = program(
            target_path="hello.py",
            retrieved_siblings="(no siblings)",
            item_class="Greeting",
            service_label="Greeting Service",
            integration_extra="just print hello",
        )

    assert hasattr(pred, "file_contents")
    assert isinstance(pred.file_contents, str)
    assert pred.file_contents.strip()
