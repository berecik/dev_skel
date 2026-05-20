"""DSPy metrics for the skel_rag programs.

A metric is a callable ``(example, pred, trace=None) -> float`` that
DSPy optimizers (``BootstrapFewShot``, ``MIPROv2``, etc.) use to score
program outputs.

Two metrics live here:

* :func:`metric_tests_pass` — binary 1.0/0.0. Closes the loop on the
  "all-or-nothing" pizzeria gate. Useful when the trainset is small
  and a single failing test invalidates the run.
* :func:`metric_pass_ratio` — graded ``passed / (passed + failed)``.
  Sharper reward signal for optimizers that converge faster on a
  continuous score (BootstrapFewShotWithRandomSearch, MIPROv2).
  Falls back to binary when the test output cannot be parsed.

The parser :func:`parse_pytest_summary` is exposed separately so
downstream code (e.g. ``run_test_generation_phase``) can use the same
counting logic for progress reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PytestSummary:
    """Parsed pytest summary line counts.

    ``passed + failed + errors + skipped == total``; ``unknown`` is set
    when the parser could not find a summary line at all (e.g. infra
    error before any test ran).
    """

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    unknown: bool = False

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped

    @property
    def all_green(self) -> bool:
        return (
            not self.unknown
            and self.failed == 0
            and self.errors == 0
            and self.passed >= 0
        )


# Pytest's terminal lines look like one of:
#   "5 failed, 56 passed, 10 warnings in 9.80s"
#   "61 passed in 9.50s"
#   "1 error in 0.15s"
#   "no tests ran in 0.05s"
# Use independent regex captures per category so the order doesn't
# matter — pytest groups by category but never guarantees the order.
_PYTEST_PASSED = re.compile(r"(\d+)\s+passed")
_PYTEST_FAILED = re.compile(r"(\d+)\s+failed")
_PYTEST_ERRORS = re.compile(r"(\d+)\s+error(?:s)?\b")
_PYTEST_SKIPPED = re.compile(r"(\d+)\s+skipped")
# Anchor on "in N.NNs" so we only count summary line(s), not lines
# inside the test names themselves (e.g. test_3_failed_to_load).
_PYTEST_TAIL = re.compile(r"in\s+\d+(?:\.\d+)?s")


def parse_pytest_summary(test_output: str) -> PytestSummary:
    """Parse ``X passed, Y failed, Z errors`` lines from pytest output.

    The function scans every line of *test_output* (not just the tail)
    looking for the "... in N.NNs" terminator and reads the counts from
    that line. When no such line exists, returns ``unknown=True`` so
    the graded metric can fall back to the binary verdict.
    """

    if not test_output:
        return PytestSummary(unknown=True)

    summary_lines = [
        ln for ln in test_output.splitlines() if _PYTEST_TAIL.search(ln)
    ]
    if not summary_lines:
        return PytestSummary(unknown=True)

    # Take the LAST summary line. pytest may emit a per-module summary
    # earlier and the final wall-clock summary at the very end; the
    # final one is the authoritative one for the whole run.
    line = summary_lines[-1]

    def _read(pattern: re.Pattern[str]) -> int:
        m = pattern.search(line)
        return int(m.group(1)) if m else 0

    return PytestSummary(
        passed=_read(_PYTEST_PASSED),
        failed=_read(_PYTEST_FAILED),
        errors=_read(_PYTEST_ERRORS),
        skipped=_read(_PYTEST_SKIPPED),
        unknown=False,
    )


def metric_tests_pass(example: Any, pred: Any, trace: Any = None) -> float:
    """Return 1.0 if ``pred.passed`` is truthy, else 0.0.

    Compatible with DSPy's optimizer metric signature
    ``metric(example, pred, trace=None)``. The ``example`` argument is
    accepted for signature compatibility but unused — the
    :class:`TestFixLoop` already produces a self-contained
    pass/fail verdict in its returned ``Prediction``.
    """

    return 1.0 if getattr(pred, "passed", False) else 0.0


def metric_pass_ratio(example: Any, pred: Any, trace: Any = None) -> float:
    """Graded ``passed / (passed + failed + errors)`` score in [0, 1].

    Behaviour:

    * If ``pred.passed`` is truthy → 1.0 (skips the parse entirely).
    * Else parse ``pred.output`` for pytest's summary line and return
      ``passed / (passed + failed + errors)``.
    * If the parse fails (no summary line) → 0.0 to match the binary
      metric, so a misconfigured trainset never silently rewards an
      infra failure.

    Why graded matters: optimizers (BootstrapFewShotWithRandomSearch,
    MIPROv2) converge much faster on a continuous signal. With a 0/1
    metric, the optimizer has to find an EXACT-pass demo before any
    reward shows up — costly when each "trial" is a full skel-gen-ai
    run that may legitimately leave 2/56 tests failing while still
    being a 50% improvement over the previous demo.
    """

    if getattr(pred, "passed", False):
        return 1.0
    output = getattr(pred, "output", "") or ""
    summary = parse_pytest_summary(output)
    if summary.unknown:
        return 0.0
    denominator = summary.passed + summary.failed + summary.errors
    if denominator == 0:
        return 0.0
    return summary.passed / denominator
