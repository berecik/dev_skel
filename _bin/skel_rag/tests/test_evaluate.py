"""Tests for :mod:`skel_rag.programs.evaluate`.

The harness wraps ``dspy.Evaluate`` but the public surface we care
about is the *return type*: a float in [0, 1]. We stub the underlying
program so the tests do not need Ollama — only the metric reduction
and the devset-building helper are exercised here.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")  # noqa: E402

from skel_rag.programs.evaluate import (  # noqa: E402
    build_devset_from_wrappers,
    evaluate_test_fix_loop,
)


class _ConstantProgram(dspy.Module):
    """Returns a fixed Prediction regardless of inputs.

    Lets us assert that the harness drives the metric, not the
    underlying LM. Each call sees the same ``passed`` and ``output``
    so the mean over the devset is deterministic.
    """

    def __init__(self, *, passed: bool, output: str = "") -> None:
        super().__init__()
        self._passed = passed
        self._output = output

    def forward(self, **_kwargs):
        return dspy.Prediction(passed=self._passed, output=self._output)


def _example(label: str) -> dspy.Example:
    """Build a minimal Example matching the TestFixLoop input list."""

    return dspy.Example(
        label=label,
        service_dir=Path("/tmp/does-not-matter"),
        run_tests=lambda: (True, ""),
        list_offending_files=lambda _o: [],
    ).with_inputs("run_tests", "list_offending_files", "service_dir")


def test_evaluate_returns_one_for_all_passing_program() -> None:
    devset = [_example("a"), _example("b"), _example("c")]
    program = _ConstantProgram(passed=True)
    score = evaluate_test_fix_loop(program=program, devset=devset)
    assert score == 1.0


def test_evaluate_returns_zero_for_unparseable_failure() -> None:
    devset = [_example("a"), _example("b")]
    program = _ConstantProgram(passed=False, output="garbage\n")
    score = evaluate_test_fix_loop(program=program, devset=devset)
    assert score == 0.0


def test_evaluate_uses_graded_metric_by_default() -> None:
    """A graded score (56/61 ≈ 0.918) must surface through the harness,
    not get binarised by the default reducer."""

    devset = [_example("a")]
    program = _ConstantProgram(
        passed=False, output="5 failed, 56 passed, 10 warnings in 9.80s",
    )
    score = evaluate_test_fix_loop(program=program, devset=devset)
    assert 0.91 < score < 0.93


def test_evaluate_raises_on_empty_devset() -> None:
    program = _ConstantProgram(passed=True)
    with pytest.raises(ValueError):
        evaluate_test_fix_loop(program=program, devset=[])


def test_build_devset_attaches_caller_factories(tmp_path: Path) -> None:
    """The two factory callables must be invoked once per wrapper, with
    that wrapper as the only arg, and the returned callables must
    surface as ``.run_tests`` and ``.list_offending_files`` on the
    Example. This is the contract the runner depends on."""

    wrappers = [tmp_path / "w1", tmp_path / "w2"]
    for w in wrappers:
        w.mkdir()

    seen_run_tests: list[Path] = []
    seen_list_offending: list[Path] = []

    def _run_tests_factory(wrapper):
        seen_run_tests.append(wrapper)
        return lambda: (True, "")

    def _list_offending_factory(wrapper):
        seen_list_offending.append(wrapper)
        return lambda _o: []

    examples = build_devset_from_wrappers(
        wrappers,
        run_tests_factory=_run_tests_factory,
        list_offending_factory=_list_offending_factory,
    )

    assert seen_run_tests == wrappers
    assert seen_list_offending == wrappers
    assert len(examples) == 2
    assert callable(examples[0].run_tests)
    assert callable(examples[0].list_offending_files)
    assert examples[0].service_dir == wrappers[0]
    assert examples[0].label == wrappers[0].name
