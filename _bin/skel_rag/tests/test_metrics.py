"""Phase-6: metric_tests_pass turns a TestFixLoop Prediction into a
DSPy-compatible 0.0/1.0 score so Phase 7's BootstrapFewShot optimizer
can drive the test/fix prompt.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from skel_rag.programs.metrics import metric_tests_pass  # noqa: E402


def test_metric_returns_one_when_passed_is_true() -> None:
    pred = types.SimpleNamespace(passed=True)
    assert metric_tests_pass(None, pred) == 1.0


def test_metric_returns_zero_when_passed_is_false() -> None:
    pred = types.SimpleNamespace(passed=False)
    assert metric_tests_pass(None, pred) == 0.0


def test_metric_returns_zero_when_passed_attr_missing() -> None:
    """A defensively-built Prediction without ``passed`` should score 0."""

    pred = types.SimpleNamespace(iterations=3)
    assert metric_tests_pass(None, pred) == 0.0


def test_metric_accepts_trace_kwarg() -> None:
    """DSPy passes a ``trace`` argument when running in optimizer
    mode. The metric must accept it without error.
    """

    pred = types.SimpleNamespace(passed=True)
    assert metric_tests_pass(None, pred, trace=[("step", "data")]) == 1.0


# --------------------------------------------------------------------- #
#  parse_pytest_summary + metric_pass_ratio (graded reward signal)
# --------------------------------------------------------------------- #

from skel_rag.programs.metrics import (  # noqa: E402
    metric_pass_ratio,
    parse_pytest_summary,
)


def test_parse_summary_typical_mixed_line() -> None:
    """The canonical pytest tail with passes + fails + warnings."""

    summary = parse_pytest_summary(
        "============== short test summary info ==============\n"
        "FAILED tests/test_foo.py::test_a - AssertionError\n"
        "5 failed, 56 passed, 10 warnings in 9.80s\n"
    )
    assert summary.passed == 56
    assert summary.failed == 5
    assert summary.errors == 0
    assert summary.skipped == 0
    assert summary.all_green is False


def test_parse_summary_only_passes() -> None:
    summary = parse_pytest_summary("61 passed in 9.50s\n")
    assert summary.passed == 61
    assert summary.failed == 0
    assert summary.all_green is True


def test_parse_summary_only_errors() -> None:
    """Collection error: pytest reports `1 error in N.NNs`."""

    summary = parse_pytest_summary(
        "ERROR tests/test_x.py - ImportError\n"
        "1 error in 0.15s\n"
    )
    assert summary.errors == 1
    assert summary.passed == 0
    assert summary.all_green is False


def test_parse_summary_unknown_when_no_tail() -> None:
    """No summary line found → ``unknown=True``.

    The metric falls back to 0.0 in that branch, which prevents an
    infra failure from silently scoring as success.
    """

    summary = parse_pytest_summary(
        "Traceback (most recent call last):\n  ...crash...\n"
    )
    assert summary.unknown is True


def test_pass_ratio_returns_one_when_passed_attr_truthy() -> None:
    """``pred.passed`` short-circuits the parse — keeps the harness
    cheap for already-green runs."""

    pred = types.SimpleNamespace(passed=True, output="9 failed, 0 passed in 1s")
    assert metric_pass_ratio(None, pred) == 1.0


def test_pass_ratio_is_graded_on_partial_pass() -> None:
    """5 failed, 56 passed → 56 / (56+5+0) ≈ 0.918. The graded
    reward lets BootstrapFewShotWithRandomSearch see incremental
    progress instead of waiting for an all-green demo.
    """

    pred = types.SimpleNamespace(
        passed=False,
        output="5 failed, 56 passed, 10 warnings in 9.80s",
    )
    score = metric_pass_ratio(None, pred)
    assert 0.91 < score < 0.93


def test_pass_ratio_zero_on_unparseable_output() -> None:
    """Defensive: no summary → 0.0 even though ``passed`` is False."""

    pred = types.SimpleNamespace(passed=False, output="kaboom\n")
    assert metric_pass_ratio(None, pred) == 0.0


def test_pass_ratio_zero_when_no_tests_at_all() -> None:
    """Counts add up to 0 → return 0.0 instead of dividing by zero."""

    pred = types.SimpleNamespace(passed=False, output="no tests ran in 0.05s")
    assert metric_pass_ratio(None, pred) == 0.0
