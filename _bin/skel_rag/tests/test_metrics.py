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
