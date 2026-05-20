"""Phase-6: TestFixLoop is a DSPy Module that runs tests, patches
failing files via :class:`FixFailingFile`, and re-runs until tests
pass or ``max_iter`` is exhausted.

We stub ``dspy.Predict`` so the unit tests do not need Ollama — only
the loop semantics (when to call fix, when to write files, when to
re-run tests) are exercised here. The live end-to-end gate is the
pizzeria suite (deferred to Phase 8 when SKEL_RAG_USE_DSPY=1 is
flipped on by default).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

dspy = pytest.importorskip("dspy")


class _StubPredictor:
    """Callable double for ``dspy.Predict(...)``.

    Each call pops the next output from ``side_effect`` and records its
    kwargs. Raises if called more times than there are outputs so the
    test fails noisily on over-invocation rather than silently
    returning ``None``.
    """

    def __init__(self, outputs: list) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def __call__(self, **kwargs):  # noqa: D401 — DSPy call surface
        self.calls.append(kwargs)
        if not self.outputs:
            raise AssertionError("Predictor called more times than expected")
        return self.outputs.pop(0)


def _make_loop(
    fix_outputs,
    *,
    max_iter: int = 3,
    num_parallel: int = 1,
    fix_attempts: int = 1,
    retriever=None,
):
    """Construct a :class:`TestFixLoop` with the fix step stubbed.

    The current ``TestFixLoop`` prefers ``dspy.ChainOfThought`` for
    its ``self.fix`` predictor (so the model emits a reasoning trace
    alongside the patched contents) and falls back to ``dspy.Predict``
    if ChainOfThought cannot be constructed. We stub *both* so the
    unit tests do not need Ollama. The ``fix_attempts`` kwarg defaults
    to 1 here to keep the legacy semantics: one LM call per file per
    iteration. Tests that exercise the per-file retry budget pass a
    larger value explicitly.

    Returns ``(loop, fix_stub)`` so the test can introspect the call
    sequence.
    """

    from skel_rag.programs.test_fix_loop import TestFixLoop

    fix_stub = _StubPredictor(fix_outputs)

    def _fake_factory(signature):
        name = getattr(signature, "__name__", "")
        if name == "FixFailingFile":
            return fix_stub
        raise AssertionError(f"unexpected signature: {name!r}")

    with patch("dspy.Predict", side_effect=_fake_factory), \
            patch("dspy.ChainOfThought", side_effect=_fake_factory):
        loop = TestFixLoop(
            max_iter=max_iter,
            num_parallel=num_parallel,
            fix_attempts=fix_attempts,
            retriever=retriever,
        )
    return loop, fix_stub


def test_passes_on_first_iter_skips_fix_entirely(tmp_path: Path) -> None:
    """run_tests returns (True, "") immediately → no fix calls, no
    files written, iterations == 0, passed=True."""

    loop, fix_stub = _make_loop(fix_outputs=[])

    def _run_tests():
        return True, ""

    def _list_offending(_output):
        raise AssertionError(
            "list_offending_files must not be called when tests pass"
        )

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is True
    assert pred.iterations == 0
    assert pred.fixes_failed == []
    # No files should have been created.
    assert list(tmp_path.iterdir()) == []
    # Fix predictor must not have been called.
    assert len(fix_stub.calls) == 0


def test_fixes_one_file_then_passes(tmp_path: Path) -> None:
    """First test run fails; one offending file is patched; second
    test run passes. iterations == 1, fixed file is on disk."""

    fix_outputs = [SimpleNamespace(fixed_contents="def hello(): return 1")]
    loop, fix_stub = _make_loop(fix_outputs=fix_outputs)

    # Stateful test runner: fail once, then pass.
    call_count = {"n": 0}

    def _run_tests():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return False, "AssertionError: hello returned 0"
        return True, ""

    def _list_offending(_output):
        return [("hello.py", "def hello(): return 0", "")]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is True
    assert pred.iterations == 1
    assert (tmp_path / "hello.py").read_text() == "def hello(): return 1"
    assert pred.fixes_failed == []
    # Fix predictor was called exactly once with the expected kwargs.
    assert len(fix_stub.calls) == 1
    call = fix_stub.calls[0]
    assert call["file_path"] == "hello.py"
    assert call["current_contents"] == "def hello(): return 0"
    assert "AssertionError" in call["test_output"]


def test_max_iter_reached_still_failing(tmp_path: Path) -> None:
    """When run_tests never passes, the loop runs the test command
    max_iter+1 times (one per iter + one final), returns passed=False,
    iterations == max_iter."""

    # Provide enough fix outputs so each iter can patch the offending
    # file. The fix_outputs list is deliberately longer than max_iter
    # so the predictor never runs dry.
    fix_outputs = [
        SimpleNamespace(fixed_contents=f"# attempt {i}\n") for i in range(5)
    ]
    loop, fix_stub = _make_loop(fix_outputs=fix_outputs, max_iter=2)

    test_calls = {"n": 0}

    def _run_tests():
        test_calls["n"] += 1
        return False, "still failing"

    def _list_offending(_output):
        return [("broken.py", "# broken\n", "")]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is False
    assert pred.iterations == 2  # max_iter
    # run_tests called once per iter + one final = max_iter + 1 = 3.
    assert test_calls["n"] == 3
    # Two fix iterations, one file each = 2 fix predict calls.
    assert len(fix_stub.calls) == 2
    # The last written contents are from the second iter (index 1).
    assert (tmp_path / "broken.py").read_text() == "# attempt 1\n"


def test_write_failure_recorded_in_fixes_failed(tmp_path: Path) -> None:
    """When the on-disk write raises (e.g. permission error), the
    failure is appended to ``fixes_failed`` and the loop continues."""

    fix_outputs = [SimpleNamespace(fixed_contents="# patched\n")]
    loop, _fix_stub = _make_loop(fix_outputs=fix_outputs, max_iter=1)

    def _run_tests():
        return False, "boom"

    def _list_offending(_output):
        return [("nested/path.py", "old\n", "")]

    # Patch ``Path.write_text`` so the destination write raises. We
    # restrict the patch to the destination we care about so the
    # mkdir() call in the loop body is unaffected.
    original_write_text = Path.write_text

    def _fake_write_text(self, *args, **kwargs):
        if self.name == "path.py":
            raise PermissionError("denied")
        return original_write_text(self, *args, **kwargs)

    with patch.object(Path, "write_text", _fake_write_text):
        pred = loop.forward(
            run_tests=_run_tests,
            list_offending_files=_list_offending,
            service_dir=tmp_path,
        )

    assert pred.passed is False
    assert any("PermissionError" in entry for entry in pred.fixes_failed)


def test_predict_exception_recorded_in_fixes_failed(tmp_path: Path) -> None:
    """When the LM call itself raises every retry, the failure is
    recorded and the next offending file in the same iteration is
    still processed.

    Constructed with ``fix_attempts=1`` so a raising stub doesn't get
    retried within the same iteration — the legacy "predict raised →
    skip file" behaviour is preserved.
    """

    class _RaisingStub:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("ollama exploded")
            return SimpleNamespace(fixed_contents="# salvaged\n")

    raising_stub = _RaisingStub()

    def _fake_factory(signature):
        return raising_stub

    from skel_rag.programs.test_fix_loop import TestFixLoop

    with patch("dspy.Predict", side_effect=_fake_factory), \
            patch("dspy.ChainOfThought", side_effect=_fake_factory):
        loop = TestFixLoop(max_iter=1, fix_attempts=1)

    def _run_tests():
        return False, "boom"

    def _list_offending(_output):
        return [
            ("a.py", "# a\n", ""),
            ("b.py", "# b\n", ""),
        ]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is False
    assert any(
        "ollama exploded" in entry for entry in pred.fixes_failed
    )
    # b.py should still have been patched after a.py's predict raised.
    assert (tmp_path / "b.py").read_text() == "# salvaged\n"


# --------------------------------------------------------------------- #
#  Phase-7+ additions: ChainOfThought reasoning, per-file retry budget,
#  parallel fan-out, retrieval-backed sibling_context.
# --------------------------------------------------------------------- #


def test_uses_chain_of_thought_by_default(tmp_path: Path) -> None:
    """The constructor must call ``dspy.ChainOfThought(FixFailingFile)``,
    NOT a bare ``dspy.Predict``. CoT adds the reasoning trace the
    optimizer (BootstrapFewShot / MIPROv2) scores against.

    We stub ChainOfThought to record the signature it was constructed
    with, and assert dspy.Predict was never reached for FixFailingFile.
    """

    from skel_rag.programs.test_fix_loop import TestFixLoop

    cot_calls: list = []
    predict_calls: list = []

    def _cot_factory(signature):
        cot_calls.append(getattr(signature, "__name__", ""))
        return _StubPredictor(
            [SimpleNamespace(fixed_contents="# ok\n")]
        )

    def _predict_factory(signature):
        predict_calls.append(getattr(signature, "__name__", ""))
        raise AssertionError(
            "TestFixLoop must prefer ChainOfThought, not Predict"
        )

    with patch("dspy.ChainOfThought", side_effect=_cot_factory), \
            patch("dspy.Predict", side_effect=_predict_factory):
        TestFixLoop(max_iter=1)

    assert cot_calls == ["FixFailingFile"]
    assert predict_calls == []


def test_in_place_retry_recovers_from_empty_output(tmp_path: Path) -> None:
    """An empty first response triggers an in-place retry inside the
    SAME outer iteration. The legacy loop dropped empty fixes into
    ``fixes_failed`` and would have wasted a full test re-run on the
    next iter; the new ``fix_attempts`` budget makes that recovery
    free.
    """

    fix_outputs = [
        SimpleNamespace(fixed_contents=""),               # first try: empty
        SimpleNamespace(fixed_contents="def hello(): return 1"),  # retry
    ]
    loop, fix_stub = _make_loop(fix_outputs=fix_outputs, fix_attempts=2)

    call_count = {"n": 0}

    def _run_tests():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return False, "AssertionError: hello returned 0"
        return True, ""

    def _list_offending(_output):
        return [("hello.py", "def hello(): return 0", "")]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is True
    assert pred.iterations == 1
    assert (tmp_path / "hello.py").read_text() == "def hello(): return 1"
    # Two predictor calls (empty + retry) but only one outer iter.
    assert len(fix_stub.calls) == 2
    assert pred.fixes_failed == []


def test_empty_after_all_retries_is_reported(tmp_path: Path) -> None:
    """When every retry produces an empty response, the file lands in
    ``fixes_failed`` with the canonical 'empty fix output' reason.
    """

    fix_outputs = [
        SimpleNamespace(fixed_contents=""),
        SimpleNamespace(fixed_contents="   \n"),
    ]
    loop, fix_stub = _make_loop(
        fix_outputs=fix_outputs, max_iter=1, fix_attempts=2,
    )

    def _run_tests():
        return False, "boom"

    def _list_offending(_output):
        return [("broken.py", "# old\n", "")]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is False
    assert any(
        "broken.py" in entry and "empty fix output" in entry
        for entry in pred.fixes_failed
    )
    # Both retries were spent, file was never written.
    assert len(fix_stub.calls) == 2
    assert not (tmp_path / "broken.py").exists()


def test_parallel_fan_out_writes_all_files(tmp_path: Path) -> None:
    """With ``num_parallel >= 2`` and multiple offending files, every
    file is written by the end of the iteration with the *right* fix
    content. We use a path-keyed stub (not a queue) because under a
    ThreadPoolExecutor the queue's pop order is non-deterministic;
    correlating output to file_path is exactly what production code
    must do.
    """

    from skel_rag.programs.test_fix_loop import TestFixLoop

    fix_calls: list[dict] = []

    class _KeyedStub:
        """Returns ``# {basename}-fix\n`` so the assertion below is
        order-independent regardless of thread scheduling."""

        def __call__(self, **kwargs):
            fix_calls.append(kwargs)
            name = kwargs["file_path"].rsplit(".", 1)[0]
            return SimpleNamespace(fixed_contents=f"# {name}-fix\n")

    keyed_stub = _KeyedStub()

    def _factory(signature):
        return keyed_stub

    with patch("dspy.ChainOfThought", side_effect=_factory), \
            patch("dspy.Predict", side_effect=_factory):
        loop = TestFixLoop(max_iter=1, num_parallel=3, fix_attempts=1)

    call_count = {"n": 0}

    def _run_tests():
        call_count["n"] += 1
        # Fail on first run, pass once all three files are patched.
        if call_count["n"] == 1:
            return False, "AssertionError"
        return True, ""

    def _list_offending(_output):
        return [
            ("a.py", "# a\n", ""),
            ("b.py", "# b\n", ""),
            ("c.py", "# c\n", ""),
        ]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is True
    assert (tmp_path / "a.py").read_text() == "# a-fix\n"
    assert (tmp_path / "b.py").read_text() == "# b-fix\n"
    assert (tmp_path / "c.py").read_text() == "# c-fix\n"
    assert len(fix_calls) == 3


def test_retriever_populates_empty_sibling_context(tmp_path: Path) -> None:
    """When the caller passes an empty ``sibling_context`` and a
    retriever is configured, ``self.fix`` receives a non-empty
    ``sibling_context`` derived from the retriever's passages.
    """

    fix_outputs = [SimpleNamespace(fixed_contents="# fixed\n")]

    class _StubRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def __call__(self, query: str):
            self.queries.append(query)
            return SimpleNamespace(
                passages=[
                    "class WrapperUser(SQLModel, table=True): ...",
                    "def get_session(): ...",
                ]
            )

    retriever = _StubRetriever()
    loop, fix_stub = _make_loop(
        fix_outputs=fix_outputs,
        max_iter=1,
        fix_attempts=1,
        retriever=retriever,
    )

    call_count = {"n": 0}

    def _run_tests():
        call_count["n"] += 1
        return (call_count["n"] != 1, "AssertionError: missing import")

    def _list_offending(_output):
        # Caller passes empty sibling_context — retriever should fill it.
        return [("svc.py", "def svc():\n    return WrapperUser()\n", "")]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is True
    assert len(retriever.queries) == 1, "retriever should be queried once"
    # The query must mention the failing file's path AND the test output
    # so the retriever can rank chunks relevant to BOTH the symbol and
    # the error.
    assert "svc.py" in retriever.queries[0]
    assert "missing import" in retriever.queries[0]
    # The fix predictor saw the enriched sibling_context.
    assert len(fix_stub.calls) == 1
    sibling = fix_stub.calls[0]["sibling_context"]
    assert "WrapperUser" in sibling
    assert "get_session" in sibling


def test_retriever_not_called_when_caller_supplies_sibling(tmp_path: Path) -> None:
    """When the caller already provides a non-empty ``sibling_context``,
    the retriever must NOT be invoked — caller intent wins.
    """

    fix_outputs = [SimpleNamespace(fixed_contents="# fixed\n")]

    class _StubRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def __call__(self, query: str):
            self.queries.append(query)
            return SimpleNamespace(passages=["should-not-be-used"])

    retriever = _StubRetriever()
    loop, fix_stub = _make_loop(
        fix_outputs=fix_outputs, max_iter=1, retriever=retriever,
    )

    call_count = {"n": 0}

    def _run_tests():
        call_count["n"] += 1
        return (call_count["n"] != 1, "fail")

    def _list_offending(_output):
        return [("svc.py", "# old\n", "explicit caller-provided context")]

    loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert retriever.queries == []
    assert (
        fix_stub.calls[0]["sibling_context"]
        == "explicit caller-provided context"
    )


def test_loop_captures_fix_attempt_with_post_test_output(
    tmp_path: Path, monkeypatch
) -> None:
    """End-to-end capture: when the env var is set the loop writes one
    JSONL record per applied fix, with the ``post_test_output``
    field populated from the NEXT iteration's test output. This is
    what lets BootstrapFewShotWithRandomSearch + metric_pass_ratio
    train without any manual annotation.
    """

    capture_dest = tmp_path / "fix.jsonl"
    monkeypatch.setenv("SKEL_RAG_CAPTURE_FIX_TRAINSET", str(capture_dest))
    monkeypatch.delenv("SKEL_RAG_CAPTURE_TRAINSET", raising=False)

    fix_outputs = [SimpleNamespace(fixed_contents="def hello(): return 1\n")]
    loop, _fix_stub = _make_loop(fix_outputs=fix_outputs)

    call_count = {"n": 0}

    def _run_tests():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return False, "AssertionError: hello returned 0"
        return True, "1 passed in 0.05s"

    def _list_offending(_output):
        return [("hello.py", "def hello(): return 0", "from app import baz")]

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is True

    import json
    lines = [
        json.loads(ln) for ln in
        capture_dest.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert len(lines) == 1
    rec = lines[0]
    assert rec["inputs"]["file_path"] == "hello.py"
    assert rec["inputs"]["current_contents"] == "def hello(): return 0"
    assert "AssertionError" in rec["inputs"]["test_output"]
    # The retriever was None, so sibling_context is the caller-supplied
    # string verbatim (not blanked or overwritten).
    assert rec["inputs"]["sibling_context"] == "from app import baz"
    assert rec["fixed_contents"] == "def hello(): return 1\n"
    # The crucial part: post_test_output is the NEXT iteration's output,
    # which is what metric_pass_ratio reads to compute the reward.
    assert rec["post_test_output"] == "1 passed in 0.05s"


def test_no_offending_files_breaks_out_immediately(tmp_path: Path) -> None:
    """When ``list_offending_files`` yields nothing, the loop must not
    spin on the same failure — it breaks out to the final run.
    Without this guard the loop would run max_iter+1 test commands
    for free on a hopeless failure (e.g. infra error).
    """

    loop, fix_stub = _make_loop(fix_outputs=[], max_iter=5)

    test_calls = {"n": 0}

    def _run_tests():
        test_calls["n"] += 1
        return False, "infra blew up"

    def _list_offending(_output):
        return []  # nothing to patch

    pred = loop.forward(
        run_tests=_run_tests,
        list_offending_files=_list_offending,
        service_dir=tmp_path,
    )

    assert pred.passed is False
    # One test run in the loop body + one final = 2, not max_iter+1.
    assert test_calls["n"] == 2
    assert pred.iterations == 5
    assert len(fix_stub.calls) == 0
