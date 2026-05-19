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


def _make_loop(fix_outputs, *, max_iter: int = 3):
    """Construct a :class:`TestFixLoop` with ``dspy.Predict`` stubbed.

    Returns ``(loop, fix_stub)`` so the test can introspect the call
    sequence.
    """

    from skel_rag.programs.test_fix_loop import TestFixLoop

    fix_stub = _StubPredictor(fix_outputs)

    def _fake_predict(signature):
        name = getattr(signature, "__name__", "")
        if name == "FixFailingFile":
            return fix_stub
        raise AssertionError(f"unexpected signature: {name!r}")

    with patch("dspy.Predict", side_effect=_fake_predict):
        loop = TestFixLoop(max_iter=max_iter)
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
    """When the LM call itself raises, the failure is recorded and the
    next offending file in the same iteration is still processed."""

    class _RaisingStub:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("ollama exploded")
            return SimpleNamespace(fixed_contents="# salvaged\n")

    raising_stub = _RaisingStub()

    def _fake_predict(signature):
        return raising_stub

    from skel_rag.programs.test_fix_loop import TestFixLoop

    with patch("dspy.Predict", side_effect=_fake_predict):
        loop = TestFixLoop(max_iter=1)

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
