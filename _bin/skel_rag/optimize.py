"""DSPy optimizer scaffolding.

``compile_generate`` runs ``BootstrapFewShot`` over a trainset of
``(gen_inputs, file_contents, passed)`` tuples and returns a compiled
``GenerateFile`` program with few-shot exemplars baked in. Persist the
result with :func:`save_compiled` and reload it with
:func:`load_compiled`. Train sets are captured during ordinary DSPy
runs when ``SKEL_RAG_CAPTURE_TRAINSET=<path>`` is set — see
:mod:`skel_rag.trainset`.

Phase 7 ships scaffolding only. The actual ``BootstrapFewShot.compile``
call is a manual operator step performed once Phase 8 has the DSPy
path as the default and the pizzeria + shared-DB suites green on it.
Driver: ``_bin/skel-rag-compile``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import dspy
from dspy.teleprompt import BootstrapFewShot

from skel_rag.programs.metrics import metric_tests_pass


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


def save_compiled(program, path: Path) -> None:
    """Persist a compiled DSPy program to disk (uses ``program.save``)."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    program.save(str(path))


def load_compiled(signature, path: Path):
    """Load a previously-saved compiled program for ``signature``."""

    student = dspy.Predict(signature)
    student.load(str(Path(path)))
    return student
