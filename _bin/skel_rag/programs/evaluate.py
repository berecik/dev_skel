"""dspy.Evaluate harness for the test/fix loop.

Wraps ``dspy.Evaluate`` so a maintainer can A/B prompt-tuning
variants (ChainOfThought on/off, retrieval on/off, num_parallel
1 vs 4, compiled demos vs not) on the same devset without writing
boilerplate. Returns a single scalar per variant so improvements are
directly comparable.

Usage example::

    from skel_rag.programs.evaluate import evaluate_test_fix_loop
    from skel_rag.programs.test_fix_loop import TestFixLoop
    from skel_rag.programs.metrics import metric_pass_ratio

    score = evaluate_test_fix_loop(
        program=TestFixLoop(max_iter=3, num_parallel=4),
        devset=load_devset(),
        metric=metric_pass_ratio,
        num_threads=2,
    )
    print(f"variant score: {score:.3f}")

The devset items must carry the ``run_tests``, ``list_offending_files``,
and ``service_dir`` inputs the loop expects. Helpers below build such
items from a known-good wrapper checkpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

import dspy

from skel_rag.programs.metrics import metric_pass_ratio


def evaluate_test_fix_loop(
    *,
    program: Any,
    devset: Sequence[Any],
    metric: Callable[..., float] = metric_pass_ratio,
    num_threads: int = 1,
    display_progress: bool = False,
) -> float:
    """Score *program* over *devset* using *metric*.

    Thin wrapper around ``dspy.Evaluate`` that keeps the same defaults
    (``metric_pass_ratio`` for graded reward, single-threaded for
    Ollama). The function returns the *mean* metric across the devset
    so caller code can store it in a CSV next to the variant config
    and pick the best one.
    """

    if not devset:
        raise ValueError("devset is empty; nothing to evaluate")
    evaluator = dspy.Evaluate(
        devset=list(devset),
        metric=metric,
        num_threads=max(1, int(num_threads)),
        display_progress=display_progress,
    )
    result = evaluator(program)
    # dspy 3.x returns either a float (0-100 percentage in current
    # releases) or an EvaluationResult depending on minor version.
    # Coerce both to a [0, 1] float so callers can compare variants
    # against the same scale the metric function emits.
    if isinstance(result, (int, float)):
        return _normalise(float(result))
    score = getattr(result, "score", None)
    if score is not None:
        return _normalise(float(score))
    # Last-ditch: average the per-example scores when DSPy returned an
    # iterable of (example, pred, metric_value) tuples.
    try:
        rows = list(result)
    except TypeError:
        return 0.0
    if not rows:
        return 0.0
    values: List[float] = []
    for row in rows:
        if isinstance(row, (int, float)):
            values.append(float(row))
        elif isinstance(row, tuple) and len(row) >= 3:
            values.append(float(row[-1]))
    return _normalise(sum(values) / len(values)) if values else 0.0


def _normalise(score: float) -> float:
    """Rescale DSPy's percentage output (0-100) back to [0, 1].

    DSPy 3.2.x's :class:`dspy.Evaluate` multiplies the metric mean by
    100 internally for human-readable display. The harness here wants
    the raw metric range so optimizer comparisons line up with the
    metric function's own scale.
    """

    if score > 1.0:
        return score / 100.0
    return score


def build_devset_from_wrappers(
    wrappers: Sequence[Path],
    *,
    run_tests_factory: Callable[[Path], Callable[[], tuple]],
    list_offending_factory: Callable[
        [Path], Callable[[str], List[tuple]]
    ],
    label_fn: Optional[Callable[[Path], str]] = None,
) -> List[dspy.Example]:
    """Convert a list of wrapper directories into a DSPy devset.

    Each :class:`dspy.Example` carries the three inputs the
    :class:`TestFixLoop.forward` consumes (``run_tests``,
    ``list_offending_files``, ``service_dir``) plus a free-form
    ``label`` for reporting.

    The factories let the caller plug in the project's own test runner
    and failing-file heuristic without coupling this module to the
    legacy ``skel_ai_lib`` helpers — keeps the harness reusable from
    unit tests with stub callables.
    """

    examples: List[dspy.Example] = []
    for wrapper in wrappers:
        service_dir = Path(wrapper)
        label = label_fn(service_dir) if label_fn else service_dir.name
        ex = dspy.Example(
            label=label,
            service_dir=service_dir,
            run_tests=run_tests_factory(service_dir),
            list_offending_files=list_offending_factory(service_dir),
        ).with_inputs("run_tests", "list_offending_files", "service_dir")
        examples.append(ex)
    return examples
