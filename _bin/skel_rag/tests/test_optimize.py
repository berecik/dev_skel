"""Phase-7: optimize.compile_generate / save_compiled / load_compiled
scaffold the BootstrapFewShot compilation entrypoint for GenerateFile.

These tests mock ``dspy.teleprompt.BootstrapFewShot`` and the compiled
program's ``save`` / ``load`` so they never call Ollama or touch the
network — Phase 7 ships scaffolding only; the real compile is a manual
operator step performed once Phase 8 has the DSPy path as default and
the pizzeria + shared-DB suites green on it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")

from skel_rag import optimize  # noqa: E402
from skel_rag.programs.metrics import metric_tests_pass  # noqa: E402
from skel_rag.signatures.generate_file import GenerateFile  # noqa: E402


def test_compile_generate_invokes_bootstrap_with_metric_and_demos():
    """``compile_generate`` must construct BootstrapFewShot with the
    metric callable and ``max_bootstrapped_demos`` kw, then forward the
    trainset to ``.compile(student=..., trainset=...)``."""

    sentinel_program = MagicMock(name="compiled_program")
    fake_tele = MagicMock(name="bootstrap_instance")
    fake_tele.compile.return_value = sentinel_program

    trainset = [MagicMock(name="example")]

    with patch.object(optimize, "BootstrapFewShot", return_value=fake_tele) as ctor:
        out = optimize.compile_generate(
            trainset, metric_fn=metric_tests_pass, max_bootstrapped_demos=3
        )

    ctor.assert_called_once_with(
        metric=metric_tests_pass, max_bootstrapped_demos=3
    )

    # The student must be a dspy.Predict over the GenerateFile signature.
    fake_tele.compile.assert_called_once()
    kwargs = fake_tele.compile.call_args.kwargs
    assert kwargs["trainset"] is trainset
    student = kwargs["student"]
    assert isinstance(student, dspy.Predict)

    assert out is sentinel_program


def test_compile_generate_defaults_to_metric_tests_pass():
    """When called without ``metric_fn`` the default must be
    ``metric_tests_pass`` — keeps the public API one-line callable."""

    fake_tele = MagicMock()
    fake_tele.compile.return_value = MagicMock()

    with patch.object(optimize, "BootstrapFewShot", return_value=fake_tele) as ctor:
        optimize.compile_generate([])

    args, kwargs = ctor.call_args
    assert kwargs["metric"] is metric_tests_pass
    assert kwargs["max_bootstrapped_demos"] == 4


def test_save_compiled_creates_parent_and_calls_save(tmp_path):
    program = MagicMock()
    dest = tmp_path / "nested" / "compiled.json"

    optimize.save_compiled(program, dest)

    assert dest.parent.exists()
    program.save.assert_called_once_with(str(dest))


def test_load_compiled_round_trips_through_predict_load(tmp_path):
    dest = tmp_path / "compiled.json"
    dest.write_text("{}", encoding="utf-8")

    fake_predict = MagicMock(name="predict_instance")

    with patch.object(optimize.dspy, "Predict", return_value=fake_predict) as ctor:
        out = optimize.load_compiled(GenerateFile, dest)

    ctor.assert_called_once_with(GenerateFile)
    fake_predict.load.assert_called_once_with(str(dest))
    assert out is fake_predict
