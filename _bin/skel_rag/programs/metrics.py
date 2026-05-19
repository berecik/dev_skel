"""DSPy metrics for the skel_rag programs.

A metric is a callable ``(example, pred, trace=None) -> float`` that
DSPy optimizers (``BootstrapFewShot``, ``MIPRO``, etc.) use to score
program outputs. The metric here closes the test/fix loop: a run is
worth 1.0 iff the service's tests pass after the loop completes, 0.0
otherwise.

Phase 7 wires this metric into ``BootstrapFewShot`` so the few-shot
exemplars and fix-prompt instructions can be tuned against the
pizzeria suite and other end-to-end gates without us hand-editing
the prompt text.
"""

from __future__ import annotations

from typing import Any


def metric_tests_pass(example: Any, pred: Any, trace: Any = None) -> float:
    """Return 1.0 if ``pred.passed`` is truthy, else 0.0.

    Compatible with DSPy's optimizer metric signature
    ``metric(example, pred, trace=None)``. The ``example`` argument is
    accepted for signature compatibility but unused — the
    :class:`TestFixLoop` already produces a self-contained
    pass/fail verdict in its returned ``Prediction``.
    """

    return 1.0 if getattr(pred, "passed", False) else 0.0
