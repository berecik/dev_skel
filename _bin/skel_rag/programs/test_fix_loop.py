"""Composed DSPy module for the test/fix loop.

Replaces the legacy ``run_test_and_fix_loop`` (and its per-file
``_ask_ollama_to_fix`` helper) with a declarative DSPy ``Module`` that
adds five concrete efficiency wins on top of the original loop:

1. ``dspy.ChainOfThought`` wraps the fix step so the model emits an
   explicit ``reasoning`` trace before the patched file contents. This
   reliably improves per-call fix accuracy and gives optimizers
   (BootstrapFewShot, MIPROv2) a signal to score against.
2. Per-file retry budget (``fix_attempts``): empty / exception
   responses get re-tried in-place instead of being given up after one
   shot. The legacy loop would drop empty fixes into ``fixes_failed``
   and continue to the next iteration of the outer test loop, wasting
   an entire test re-run on a recoverable LM hiccup.
3. ``num_parallel`` per-iteration file fan-out via
   ``ThreadPoolExecutor``. Ollama serves one request per loaded model
   at a time by default, but with ``OLLAMA_NUM_PARALLEL`` >= 2 on the
   server the fixes for distinct files overlap on GPU. Default 1
   matches the legacy serial behaviour exactly.
4. Retrieval-backed ``sibling_context``: when a
   :class:`dspy.Retrieve`-compatible retriever is provided, each
   failing file's ``sibling_context`` is populated with relevant
   chunks from the project corpus (e.g. the wrapper-shared models
   that the failing import refers to). The legacy loop only included
   a couple of hard-coded module paths.
5. Auto-load of BootstrapFewShot-compiled demos from
   ``_bin/skel_rag/compiled/fix_failing.json`` when present, so a
   one-time offline tune carries forward into every subsequent run
   for free.

All five additions degrade gracefully: if ``ChainOfThought`` cannot
import, if the retriever is unset, or if the compiled artefact is
missing, the module still runs the legacy "predict once, write file,
re-run" cycle.

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

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Tuple

import dspy

from skel_rag.signatures.fix_failing import FixFailingFile


# Type aliases for the two adapter callables the program expects.
RunTestsFn = Callable[[], Tuple[bool, str]]
ListOffendingFn = Callable[[str], Iterable[Tuple[Any, str, str]]]

# Compiled-demos artefact location. The on-disk format is whatever
# ``dspy.Module.save(...)`` writes — usually a JSON containing the
# bootstrapped demos for each Predict step.
_COMPILED_FIX_PATH = (
    Path(__file__).resolve().parent.parent / "compiled" / "fix_failing.json"
)


def _build_fix_module() -> Any:
    """Return the per-file fix predictor.

    Prefer :class:`dspy.ChainOfThought` so the model produces a
    reasoning trace alongside ``fixed_contents``; fall back to a bare
    ``dspy.Predict`` if ChainOfThought cannot be constructed (older
    DSPy versions or custom adapters that reject Literal output
    fields).
    """

    try:
        return dspy.ChainOfThought(FixFailingFile)
    except Exception:  # noqa: BLE001 — best-effort fallback
        return dspy.Predict(FixFailingFile)


class TestFixLoop(dspy.Module):
    """Run tests, patch failing files via DSPy, repeat up to ``max_iter``.

    The program does NOT know how to run a project's tests or how to
    parse "which files failed" from the output — those are caller
    responsibilities passed in as the ``run_tests`` and
    ``list_offending_files`` callables. That keeps the program
    framework-agnostic: a pytest-based service, a cargo-based service,
    a flutter-based service can all be repaired by the same module
    with different adapters.

    Optional knobs:

    * ``lm`` — DSPy LM bound for the loop body (typically the FIX
      slot from :class:`OllamaConfig`).
    * ``max_iter`` — outer loop cap (default 3).
    * ``num_parallel`` — concurrent per-file fix calls (default 1,
      i.e. legacy serial). Set >1 when Ollama is configured with
      ``OLLAMA_NUM_PARALLEL`` >= num_parallel on the server.
    * ``fix_attempts`` — per-file retries on empty / exception output
      (default 2). The retry happens *within* one outer iteration so
      a transient LM hiccup does not cost a full test re-run.
    * ``retriever`` — optional ``dspy.Retrieve`` instance (e.g.
      :class:`skel_rag.dspy_retriever.SkelRagRM`). When set, the
      ``sibling_context`` passed to :class:`FixFailingFile` is built
      from retrieved corpus chunks if the caller did not provide
      one.
    """

    def __init__(
        self,
        *,
        lm: Any = None,
        max_iter: int = 3,
        num_parallel: int = 1,
        fix_attempts: int = 2,
        retriever: Any = None,
    ) -> None:
        super().__init__()
        self.fix = _build_fix_module()
        self.max_iter = max_iter
        self.num_parallel = max(1, int(num_parallel))
        self.fix_attempts = max(1, int(fix_attempts))
        self._lm = lm
        self._retriever = retriever
        self._compiled_loaded = False
        self._maybe_load_compiled()

    # ------------------------------------------------------------------ #
    #  Compiled demo loading
    # ------------------------------------------------------------------ #

    def _maybe_load_compiled(self) -> None:
        """Best-effort load of an offline-compiled fix predictor.

        Honours ``SKEL_RAG_FIX_COMPILED`` for an explicit path override;
        otherwise looks at the default ``compiled/fix_failing.json``.
        Silent no-op when the file is missing or load fails — the
        un-compiled predictor still works, just without baked-in demos.
        """

        explicit = os.environ.get("SKEL_RAG_FIX_COMPILED", "").strip()
        path = Path(explicit) if explicit else _COMPILED_FIX_PATH
        if not path.is_file():
            return
        try:
            self.fix.load(str(path))
            self._compiled_loaded = True
        except Exception:  # noqa: BLE001 — best-effort
            self._compiled_loaded = False

    # ------------------------------------------------------------------ #
    #  Sibling-context enrichment via retrieval
    # ------------------------------------------------------------------ #

    def _enrich_sibling(
        self, rel_path: str, current: str, sibling_in: str, test_output: str,
    ) -> str:
        """Return a ``sibling_context`` string, retrieving when needed.

        Order of preference:

        1. Caller-supplied ``sibling_in`` (non-empty) — used verbatim.
        2. Retriever query built from ``rel_path`` + the tail of the
           failing test output + the head of the current file contents.
        3. Empty string when neither is available.
        """

        if sibling_in:
            return sibling_in
        if self._retriever is None:
            return ""
        # Compose a focused query: the file path tells the retriever
        # what kind of code to look for; the test output tail surfaces
        # the missing symbol / failing assertion; the file head gives
        # additional grounding (imports, top-level declarations).
        query = (
            f"{rel_path}\n"
            f"{test_output[-800:]}\n"
            f"{current[:600]}"
        )
        try:
            pred = self._retriever(query=query)
        except Exception:  # noqa: BLE001 — retrieval is best-effort
            return ""
        passages = getattr(pred, "passages", None) or []
        if not passages:
            return ""
        joined = "\n\n---\n\n".join(p for p in passages[:5] if p)
        return joined[:6000]

    # ------------------------------------------------------------------ #
    #  Per-file fix with in-place retry
    # ------------------------------------------------------------------ #

    def _fix_one(
        self, rel_path: str, current: str, sibling: str, test_output: str,
    ) -> Tuple[str, str, str]:
        """Try to patch one file; retry up to ``fix_attempts`` times.

        Returns ``(status, rel_path, payload)`` where:

        * ``status == "ok"``     → ``payload`` is the new file contents.
        * ``status == "empty"``  → ``payload`` is a one-line error reason
          ("empty fix output" after exhausting retries).
        * ``status == "error"``  → ``payload`` is a one-line error reason
          ("predict raised: <exc>").
        """

        last_exc: Optional[BaseException] = None
        for _ in range(self.fix_attempts):
            try:
                pred = self.fix(
                    file_path=str(rel_path),
                    current_contents=current,
                    test_output=test_output,
                    sibling_context=sibling,
                )
            except Exception as exc:  # noqa: BLE001 — record + retry
                last_exc = exc
                continue
            fixed = getattr(pred, "fixed_contents", "") or ""
            # Emptiness check ignores whitespace, but the on-disk write
            # preserves the model's trailing newline / formatting.
            if fixed.strip():
                return ("ok", str(rel_path), fixed)
        if last_exc is not None:
            return ("error", str(rel_path), f"predict raised: {last_exc!r}")
        return ("empty", str(rel_path), "empty fix output")

    # ------------------------------------------------------------------ #
    #  Outer loop
    # ------------------------------------------------------------------ #

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
            whose LM call raised after all retries).
        """

        service_dir = Path(service_dir)
        fixes_failed: List[str] = []
        last_output = ""
        # Reset any stale captures from a previous forward() call.
        self._pending_captures = []

        # The whole iterative body runs under the optional LM context.
        # nullcontext lets the program still work with the global
        # dspy.configure() default — useful in unit tests that stub
        # dspy.Predict / dspy.ChainOfThought entirely.
        ctx = dspy.context(lm=self._lm) if self._lm else nullcontext()
        with ctx:
            for i in range(self.max_iter):
                passed, output = run_tests()
                last_output = output
                # Drain any captures from the previous iteration: the
                # test output we just got is the reward signal for
                # those fixes.
                self._drain_pending_captures(post_test_output=output)
                if passed:
                    return dspy.Prediction(
                        iterations=i,
                        passed=True,
                        output=output,
                        fixes_failed=fixes_failed,
                    )

                # Materialise the file list so we can fan it out under
                # the executor without re-running the caller's
                # generator. Then enrich sibling_context via retrieval
                # when the caller didn't already supply one.
                raw_items = list(list_offending_files(output))
                enriched = [
                    (
                        rel,
                        current,
                        self._enrich_sibling(rel, current, sibling, output),
                    )
                    for (rel, current, sibling) in raw_items
                ]

                if not enriched:
                    # Nothing to patch — re-running tests would loop on
                    # the same failure. Break out to the final run.
                    break

                # Per-iteration fan-out. Sequential by default to match
                # legacy behaviour exactly; threaded when num_parallel>1
                # and there are at least 2 distinct files.
                if self.num_parallel > 1 and len(enriched) > 1:
                    with ThreadPoolExecutor(
                        max_workers=min(self.num_parallel, len(enriched))
                    ) as pool:
                        results = list(
                            pool.map(
                                lambda item: self._fix_one(
                                    item[0], item[1], item[2], output,
                                ),
                                enriched,
                            )
                        )
                else:
                    results = [
                        self._fix_one(rel, current, sibling, output)
                        for (rel, current, sibling) in enriched
                    ]

                # Apply results: writes are still sequential (single
                # filesystem, no benefit from threading them) but never
                # block on each other across iterations.
                written_for_capture: list[tuple[str, str, str, str, str]] = []
                # tuples are (rel_path, before, after, sibling, output)
                # — used by the trainset capture below once the
                # post-fix test result is available.

                # Build a quick lookup of the inputs we already saw,
                # so the capture row can include the sibling_context
                # the LM actually received.
                input_by_path = {
                    str(rel): (current, sibling)
                    for (rel, current, sibling) in enriched
                }

                for status, rel_path, payload in results:
                    if status != "ok":
                        fixes_failed.append(f"{rel_path}: {payload}")
                        continue
                    destination = service_dir / rel_path
                    try:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_text(payload, encoding="utf-8")
                    except Exception as exc:  # noqa: BLE001
                        fixes_failed.append(
                            f"{rel_path}: write failed: {exc!r}"
                        )
                        continue
                    before, sib = input_by_path.get(rel_path, ("", ""))
                    written_for_capture.append(
                        (rel_path, before, payload, sib, output)
                    )

                # Capture each fix together with the test output that
                # follows the next loop iteration's run. That output
                # IS the reward signal — metric_pass_ratio reads it
                # directly. We defer the actual capture until the
                # NEXT iteration's run_tests() returns by stashing
                # the staged rows on self.
                self._stash_pending_captures(written_for_capture)

            # max_iter exhausted — re-run tests one last time so the
            # returned prediction reflects the on-disk state after the
            # final batch of patches.
            passed, output = run_tests()
            last_output = output
            self._drain_pending_captures(post_test_output=output)
            return dspy.Prediction(
                iterations=self.max_iter,
                passed=passed,
                output=last_output,
                fixes_failed=fixes_failed,
            )

    # ------------------------------------------------------------------ #
    #  Trainset capture (deferred so post_test_output is the reward)
    # ------------------------------------------------------------------ #

    def _stash_pending_captures(
        self, rows: List[Tuple[str, str, str, str, str]],
    ) -> None:
        """Buffer fix attempts until the next run_tests() returns.

        Each row is ``(rel_path, before, after, sibling, output)``.
        We can't write the trainset record yet because the
        post-fix test output (the reward signal for
        :func:`metric_pass_ratio`) only exists after the next
        ``run_tests`` call.
        """

        if not hasattr(self, "_pending_captures"):
            self._pending_captures = []
        self._pending_captures.extend(rows)

    def _drain_pending_captures(self, *, post_test_output: str) -> None:
        """Write stashed fix attempts with the now-known reward."""

        if not getattr(self, "_pending_captures", None):
            return
        try:
            from skel_rag.trainset import capture_fix_attempt
        except Exception:  # noqa: BLE001 — capture is best-effort
            self._pending_captures = []
            return
        for rel_path, before, after, sibling, output_in in (
            self._pending_captures
        ):
            try:
                capture_fix_attempt(
                    file_path=rel_path,
                    current_contents=before,
                    test_output=output_in,
                    sibling_context=sibling,
                    fixed_contents=after,
                    post_test_output=post_test_output,
                )
            except Exception:  # noqa: BLE001
                continue
        self._pending_captures = []
