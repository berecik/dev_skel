"""Phase-8a: ``extract_failing_paths`` returns the list of failing
source files parsed out of a test runner's output.

The function is a pure refactor of the heuristic that used to live
inline at the top of ``_fix_failing_files`` in ``skel_ai_lib.py``.
Two parsing modes:

* **Primary** — pytest-style ``FAILED tests/foo.py::bar`` lines yield
  paths under ``tests/``, ``test/``, ``src/``, ``e2e/`` directly.
* **Fallback** — when no ``FAILED`` lines appear, scan the tail of
  the output for ``File "<path>"`` / ``at <path>`` / ``in <path>`` /
  ``from <path>`` mentions of files with code-like extensions
  (.py, .ts, .tsx, .dart, .java, .rs, .go).

Paths are filtered to the service's own source tree (the allowed
prefixes are ``app/<slug>/``, ``tests/``, ``test/``, ``src/``, ``e2e/``)
and skip ``__init__.py`` / ``conftest.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


def _make_service(tmp_path: Path, slug: str = "myservice") -> Path:
    """Build a minimal service tree on disk that exercises every
    allowed prefix branch + every skip branch in
    :func:`extract_failing_paths`."""

    service = tmp_path / slug
    (service / "tests").mkdir(parents=True)
    (service / "tests" / "test_api.py").write_text("def test(): assert False\n")
    (service / "tests" / "__init__.py").write_text("")
    (service / "tests" / "conftest.py").write_text("")
    (service / f"app/{slug}").mkdir(parents=True)
    (service / f"app/{slug}/api.py").write_text("# api\n")
    (service / "src").mkdir()
    (service / "src" / "main.ts").write_text("// main\n")
    # Skipped dir — must not appear in results even when mentioned.
    (service / ".venv").mkdir()
    (service / ".venv" / "vendored.py").write_text("# vendored\n")
    return service


def test_pytest_failed_lines_yield_paths(tmp_path: Path) -> None:
    """Primary heuristic: pytest ``FAILED tests/...`` lines are the
    most reliable signal and override the fallback file-mention scan."""

    from skel_ai_lib import extract_failing_paths

    service = _make_service(tmp_path)
    output = (
        "============================== FAILURES ==============================\n"
        "_____________________________ test_api _______________________________\n"
        "tests/test_api.py:1: in <module>\n"
        "    def test(): assert False\n"
        "E   AssertionError\n"
        "==================== short test summary info ========================\n"
        "FAILED tests/test_api.py::test - AssertionError\n"
    )

    paths = extract_failing_paths(output, service, "myservice")

    assert (service / "tests" / "test_api.py") in paths
    assert len(paths) == 1


def test_falls_back_to_file_mentions_when_no_failed_line(
    tmp_path: Path,
) -> None:
    """Fallback heuristic: when nothing matches ``FAILED <path>``, the
    function scans the tail of the output for ``File "<path>"`` /
    ``in <path>`` / ``at <path>`` / ``from <path>`` mentions."""

    from skel_ai_lib import extract_failing_paths

    service = _make_service(tmp_path)
    output = (
        "Traceback (most recent call last):\n"
        '  File "src/main.ts", line 1, in <module>\n'
        '    import foo\n'
        "SyntaxError: bad token\n"
    )

    paths = extract_failing_paths(output, service, "myservice")

    assert (service / "src" / "main.ts") in paths


def test_skips_files_outside_allowed_prefixes(tmp_path: Path) -> None:
    """Files mentioned but living outside ``tests/`` ``test/`` ``src/``
    ``e2e/`` ``app/<slug>/`` must be filtered out — the .venv file
    should never appear. The fallback-of-fallback rglob may surface
    real test files instead, which is the legitimate behaviour
    (better to repair *something* than nothing); but the rejected
    .venv path must not be in the result."""

    from skel_ai_lib import extract_failing_paths

    service = _make_service(tmp_path)
    output = (
        "Traceback (most recent call last):\n"
        '  File ".venv/vendored.py", line 1, in <module>\n'
        '    do_thing()\n'
    )

    paths = extract_failing_paths(output, service, "myservice")

    assert (service / ".venv" / "vendored.py") not in paths
    for p in paths:
        assert ".venv" not in p.parts


def test_skips_init_and_conftest(tmp_path: Path) -> None:
    """``__init__.py`` and ``conftest.py`` must never appear in the
    returned list, even if pytest happens to mention them."""

    from skel_ai_lib import extract_failing_paths

    service = _make_service(tmp_path)
    output = (
        "FAILED tests/__init__.py::test_x\n"
        "FAILED tests/conftest.py::fixture_y\n"
    )

    paths = extract_failing_paths(output, service, "myservice")

    assert paths == []


def test_empty_output_returns_empty_list(tmp_path: Path) -> None:
    """An empty test output (no failures, no tracebacks) should yield
    an empty list — the fallback only fires when there are no FAILED
    lines AND no recognisable file mentions in the tail."""

    from skel_ai_lib import extract_failing_paths

    service = _make_service(tmp_path)

    paths = extract_failing_paths("", service, "myservice")

    assert paths == []
