"""Tests for ``skel_rag.chunker``.

These tests use the stdlib ``ast`` fallback for Python (so they pass on
machines without tree-sitter installed) and a tiny in-memory fixture
file. The tree-sitter path for Java / TypeScript / Rust is exercised by
the smoke verification in :mod:`test_smoke`, gated on the optional
dependency being importable.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Allow ``python _bin/skel_rag/tests/test_chunker.py`` to import the
# package without an editable install.
_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from skel_rag.chunker import (  # noqa: E402
    CodeChunker,
    detect_language,
)
from skel_rag.config import RagConfig  # noqa: E402


PYTHON_FIXTURE = '''\
"""Module docstring."""

from typing import List


def alpha(x: int) -> int:
    """Add one."""
    return x + 1


def beta(values: List[int]) -> int:
    return sum(values)


class Adder:
    """Stateful adder."""

    def __init__(self, base: int) -> None:
        self.base = base

    def add(self, x: int) -> int:
        return self.base + x
'''


class ChunkerLanguageDetectionTests(unittest.TestCase):
    def test_detects_python(self) -> None:
        self.assertEqual(detect_language(Path("foo.py")), ("python", "python"))

    def test_detects_typescript_and_tsx(self) -> None:
        self.assertEqual(detect_language(Path("a.ts")), ("typescript", "typescript"))
        self.assertEqual(detect_language(Path("a.tsx")), ("typescript", "tsx"))

    def test_detects_rust_java_and_unknown(self) -> None:
        self.assertEqual(detect_language(Path("a.rs")), ("rust", "rust"))
        self.assertEqual(detect_language(Path("a.java")), ("java", "java"))
        self.assertIsNone(detect_language(Path("README.md")))

    def test_detects_dart(self) -> None:
        # Added when `flutter-skel` shipped — make sure the chunker
        # routes .dart files to the dart parser instead of falling
        # through to the text splitter.
        self.assertEqual(detect_language(Path("main.dart")), ("dart", "dart"))


class PythonChunkerTests(unittest.TestCase):
    """Exercises the stdlib ``ast`` fallback path explicitly.

    We force the fallback by routing through ``_chunk_python_with_stdlib``
    so the test does not depend on tree-sitter being installed.
    """

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.path = self.root / "sample.py"
        self.path.write_text(PYTHON_FIXTURE, encoding="utf-8")
        self.chunker = CodeChunker(RagConfig.from_env())

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_stdlib_python_chunker_finds_functions_and_class(self) -> None:
        chunks = self.chunker._chunk_python_with_stdlib(  # type: ignore[attr-defined]
            self.path, "sample.py", PYTHON_FIXTURE
        )
        names_by_kind: dict[str, list[str]] = {}
        for chunk in chunks:
            names_by_kind.setdefault(chunk.kind, []).append(chunk.name)

        self.assertIn("function", names_by_kind)
        self.assertIn("class", names_by_kind)
        self.assertIn("alpha", names_by_kind["function"])
        self.assertIn("beta", names_by_kind["function"])
        # `add` and `__init__` are also functions in the AST view.
        self.assertIn("add", names_by_kind["function"])
        self.assertIn("Adder", names_by_kind["class"])

    def test_chunk_file_dispatches(self) -> None:
        chunks = self.chunker.chunk_file(self.path, corpus_root=self.root)
        # Either tree-sitter or the stdlib fallback should produce >0 chunks.
        self.assertTrue(chunks, "expected at least one chunk")
        for chunk in chunks:
            self.assertEqual(chunk.language, "python")
            self.assertEqual(chunk.rel_path, "sample.py")
            self.assertGreaterEqual(chunk.start_line, 1)
            self.assertGreaterEqual(chunk.end_line, chunk.start_line)
            self.assertTrue(chunk.source.strip())

    def test_chunk_metadata_round_trips(self) -> None:
        chunks = self.chunker._chunk_python_with_stdlib(  # type: ignore[attr-defined]
            self.path, "sample.py", PYTHON_FIXTURE
        )
        meta = chunks[0].to_metadata(corpus_id="test")
        self.assertEqual(meta["corpus_id"], "test")
        self.assertEqual(meta["language"], "python")
        self.assertEqual(meta["rel_path"], "sample.py")
        self.assertIn("name", meta)
        self.assertIn("start_line", meta)


class TextFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_unknown_extension_uses_fallback(self) -> None:
        path = self.root / "README.md"
        path.write_text(
            "# Title\n\nLong paragraph " * 20, encoding="utf-8"
        )
        chunks = CodeChunker(RagConfig.from_env()).chunk_file(
            path, corpus_root=self.root
        )
        self.assertTrue(chunks, "fallback path should produce at least one chunk")
        for chunk in chunks:
            self.assertEqual(chunk.language, "text")
            self.assertEqual(chunk.kind, "text_chunk")


if __name__ == "__main__":
    unittest.main()
