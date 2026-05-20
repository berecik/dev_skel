"""DSPy optimizer scaffolding.

Three compile entry points live here, in order of increasing budget:

* :func:`compile_generate` — BootstrapFewShot over the
  :class:`GenerateFile` signature. Cheap (few minutes); bakes
  successful prior outputs as few-shot exemplars. The original
  Phase 7 entry point.
* :func:`compile_fix_failing` — BootstrapFewShotWithRandomSearch
  over the :class:`FixFailingFile` (CoT-wrapped) predictor. Used
  by the new test/fix loop in
  :mod:`skel_rag.programs.test_fix_loop`. Searches over which
  demos help, no manual ``passed: true`` annotation needed because
  the metric is the actual test-pass ratio.
* :func:`compile_fix_failing_mipro` — :class:`MIPROv2` joint
  optimization of *instructions* and *demos*. Higher budget,
  larger wins; recommended for a quarterly retune rather than every
  commit.

Persist compiled programs with :func:`save_compiled` and reload them
with :func:`load_compiled`. The default on-disk location is
``_bin/skel_rag/compiled/<name>.json`` so the runtime auto-discovery
in :class:`TestFixLoop` picks them up without extra wiring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import dspy
from dspy.teleprompt import BootstrapFewShot

from skel_rag.programs.metrics import metric_pass_ratio, metric_tests_pass


# Default compiled artefact paths. Keep in sync with
# ``TestFixLoop._maybe_load_compiled`` and the runtime auto-loader.
COMPILED_DIR = Path(__file__).resolve().parent / "compiled"
DEFAULT_FIX_COMPILED = COMPILED_DIR / "fix_failing.json"
DEFAULT_GEN_COMPILED = COMPILED_DIR / "generate_file.json"


def compile_generate(
    trainset,
    metric_fn: Callable = metric_tests_pass,
    *,
    max_bootstrapped_demos: int = 4,
):
    """Compile the per-target :class:`GenerateFile` predictor.

    ``trainset`` is a list of ``dspy.Example`` objects whose
    ``.inputs()`` keys match the :class:`GenerateFile` signature
    fields. ``metric_fn`` must accept
    ``(example, pred, trace=None)`` and return a float in ``[0, 1]``.
    """

    from skel_rag.signatures.generate_file import GenerateFile

    student = dspy.Predict(GenerateFile)
    tele = BootstrapFewShot(
        metric=metric_fn,
        max_bootstrapped_demos=max_bootstrapped_demos,
    )
    return tele.compile(student=student, trainset=trainset)


def compile_fix_failing(
    trainset,
    metric_fn: Callable = metric_pass_ratio,
    *,
    max_bootstrapped_demos: int = 4,
    num_candidate_programs: int = 4,
    num_threads: int = 1,
):
    """Compile the per-file :class:`FixFailingFile` ChainOfThought.

    Uses :class:`BootstrapFewShotWithRandomSearch` so the optimizer
    *picks* which captured fixes make the best demos rather than
    baking every passing example. With the graded
    :func:`metric_pass_ratio` the search converges on demos that
    move tests from "5 failed" toward "0 failed" instead of waiting
    for an all-green example to appear.

    Arguments:
        trainset: list of ``dspy.Example`` objects whose ``.inputs()``
            keys match the :class:`FixFailingFile` signature.
        metric_fn: graded metric in ``[0, 1]``. Defaults to
            :func:`metric_pass_ratio`.
        max_bootstrapped_demos: per-program demo cap. 4 is a sane
            default; larger values bloat the prompt and slow
            inference.
        num_candidate_programs: how many demo subsets random search
            will evaluate. Each candidate costs one full devset run.
        num_threads: forwarded to the inner ``BootstrapFewShot``;
            keep at 1 for Ollama unless ``OLLAMA_NUM_PARALLEL`` is
            set on the server.
    """

    from dspy.teleprompt import BootstrapFewShotWithRandomSearch

    from skel_rag.signatures.fix_failing import FixFailingFile

    student = dspy.ChainOfThought(FixFailingFile)
    tele = BootstrapFewShotWithRandomSearch(
        metric=metric_fn,
        max_bootstrapped_demos=max_bootstrapped_demos,
        num_candidate_programs=num_candidate_programs,
        num_threads=max(1, int(num_threads)),
    )
    return tele.compile(student=student, trainset=trainset)


def compile_fix_failing_mipro(
    trainset,
    metric_fn: Callable = metric_pass_ratio,
    *,
    auto: str = "light",
    max_bootstrapped_demos: int = 4,
    num_threads: int = 1,
    valset: Optional[list] = None,
):
    """Compile :class:`FixFailingFile` with :class:`MIPROv2`.

    MIPROv2 jointly optimizes *instructions* (the prompt text itself)
    and *demos*, using a Bayesian search over both. Higher budget but
    typically beats BootstrapFewShotWithRandomSearch by another
    30-50% on Phase-6-style tasks.

    Arguments:
        trainset: list of ``dspy.Example``.
        metric_fn: graded metric.
        auto: MIPROv2 budget knob — ``"light"`` (~10 min on a small
            trainset), ``"medium"``, or ``"heavy"`` (hours).
        valset: optional separate validation set; defaults to the
            same trainset.
    """

    from dspy.teleprompt import MIPROv2

    from skel_rag.signatures.fix_failing import FixFailingFile

    student = dspy.ChainOfThought(FixFailingFile)
    tele = MIPROv2(
        metric=metric_fn,
        auto=auto,
        num_threads=max(1, int(num_threads)),
    )
    return tele.compile(
        student=student,
        trainset=trainset,
        valset=valset or trainset,
        max_bootstrapped_demos=max_bootstrapped_demos,
        requires_permission_to_run=False,
    )


def save_compiled(program: Any, path: Path) -> None:
    """Persist a compiled DSPy program to disk (uses ``program.save``)."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    program.save(str(path))


def load_compiled(signature, path: Path):
    """Load a previously-saved compiled program for ``signature``."""

    student = dspy.Predict(signature)
    student.load(str(Path(path)))
    return student
