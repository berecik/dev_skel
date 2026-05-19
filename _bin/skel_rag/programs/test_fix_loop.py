"""Composed DSPy module for the test/fix loop.

Replaces the legacy ``run_test_and_fix_loop`` (and its per-file
``_ask_ollama_to_fix`` helper) with a declarative DSPy ``Module``:

    while iter < max_iter:
        if run_tests().passed: return
        for (path, contents, sibling) in list_offending_files(output):
            pred = self.fix(...)
            write(service_dir / path, pred.fixed_contents)

The DSPy formulation lets Phase 7 wrap this in
``BootstrapFewShot(metric=metric_tests_pass)`` to auto-tune the
fix prompt against the pizzeria suite and other end-to-end gates.

Constraints baked in:

* The caller is responsible for the LM choice. The constructor takes
  an optional ``lm`` kwarg and wraps the loop body in
  ``dspy.context(lm=lm)`` so the FIX model (lower temperature, shorter
  timeout) is used instead of the default GEN model.
* File writes are wrapped in ``try/except``: one unwritable file
  must not kill the whole loop. Failed paths are collected into
  ``Prediction.fixes_failed`` so the caller can report them.
* When ``max_iter`` is reached the loop still runs the test command
  one final time so the returned ``Prediction.passed`` reflects the
  on-disk state after all patches were applied.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, Iterable, Tuple

import dspy

from skel_rag.signatures.fix_failing import FixFailingFile


# Type aliases for the two adapter callables the program expects.
RunTestsFn = Callable[[], Tuple[bool, str]]
ListOffendingFn = Callable[[str], Iterable[Tuple[Any, str, str]]]


class TestFixLoop(dspy.Module):
    """Run tests, patch failing files via DSPy, repeat up to ``max_iter``.

    The program does NOT know how to run a project's tests or how to
    parse "which files failed" from the output — those are caller
    responsibilities passed in as the ``run_tests`` and
    ``list_offending_files`` callables. That keeps the program
    framework-agnostic: a pytest-based service, a cargo-based service,
    a flutter-based service can all be repaired by the same module
    with different adapters.
    """

    def __init__(self, *, lm: Any = None, max_iter: int = 3) -> None:
        super().__init__()
        self.fix = dspy.Predict(FixFailingFile)
        self.max_iter = max_iter
        self._lm = lm

    def forward(
        self,
        run_tests: RunTestsFn,
        list_offending_files: ListOffendingFn,
        service_dir: Path,
    ) -> dspy.Prediction:
        """Run the test/fix loop and return a ``dspy.Prediction``.

        Arguments:
            run_tests: zero-arg callable returning ``(passed, output)``.
            list_offending_files: callable that takes the test output
                string and yields ``(rel_path, current_contents,
                sibling_context)`` tuples — one per file to patch.
            service_dir: the directory to write patched files into.

        Returns:
            ``dspy.Prediction`` with ``passed: bool``, ``iterations: int``,
            ``output: str`` (last test output), and
            ``fixes_failed: list[str]`` (paths whose write failed or
            whose LM call raised).
        """

        service_dir = Path(service_dir)
        fixes_failed: list[str] = []
        last_output = ""

        # The whole iterative body runs under the optional LM context.
        # We use nullcontext when no lm is given so the program still
        # works with the global dspy.configure() default — useful in
        # unit tests that stub dspy.Predict entirely.
        ctx = dspy.context(lm=self._lm) if self._lm else nullcontext()
        with ctx:
            for i in range(self.max_iter):
                passed, output = run_tests()
                last_output = output
                if passed:
                    return dspy.Prediction(
                        iterations=i,
                        passed=True,
                        output=output,
                        fixes_failed=fixes_failed,
                    )

                # Patch every offending file the caller identifies.
                # Each fix is independent — a failure on one file
                # (LM error, unwritable path) is logged into
                # ``fixes_failed`` and the loop continues.
                for rel_path, current_contents, sibling_ctx in (
                    list_offending_files(output)
                ):
                    try:
                        pred = self.fix(
                            file_path=str(rel_path),
                            current_contents=current_contents,
                            test_output=output,
                            sibling_context=sibling_ctx,
                        )
                    except Exception as exc:  # noqa: BLE001
                        fixes_failed.append(
                            f"{rel_path}: predict raised: {exc!r}"
                        )
                        continue

                    fixed = getattr(pred, "fixed_contents", "") or ""
                    if not fixed.strip():
                        fixes_failed.append(f"{rel_path}: empty fix output")
                        continue

                    destination = service_dir / rel_path
                    try:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_text(fixed, encoding="utf-8")
                    except Exception as exc:  # noqa: BLE001
                        fixes_failed.append(
                            f"{rel_path}: write failed: {exc!r}"
                        )
                        continue

            # max_iter exhausted — re-run tests one last time so the
            # returned prediction reflects the on-disk state after the
            # final batch of patches.
            passed, output = run_tests()
            last_output = output
            return dspy.Prediction(
                iterations=self.max_iter,
                passed=passed,
                output=last_output,
                fixes_failed=fixes_failed,
            )
