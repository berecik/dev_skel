"""Tests for ``skel_rag.corpus``."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from skel_rag.corpus import (  # noqa: E402
    compute_manifest,
    corpus_for_skeleton,
    corpus_for_wrapper,
    manifests_match,
)


class CorpusDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

        # Build a fake skeleton with one indexable file, one ignored
        # build dir, and one oversized file the walker should skip.
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "ignored.js").write_text(
            "skip me", encoding="utf-8"
        )
        (self.root / "README.md").write_text("# Title", encoding="utf-8")
        (self.root / "Cargo.lock").write_text("not indexable", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_corpus_includes_indexable_files_and_skips_excluded(self) -> None:
        corpus = corpus_for_skeleton(self.root)
        # Use the corpus's already-resolved root because tempfile dirs on
        # macOS live under /var/... but resolve to /private/var/... .
        rel_paths = sorted(str(p.relative_to(corpus.root)) for p in corpus.files)
        self.assertIn("src/main.py", rel_paths)
        self.assertIn("README.md", rel_paths)
        # node_modules should be filtered out, .lock files are not in
        # the indexable extension list.
        self.assertNotIn("node_modules/ignored.js", rel_paths)
        self.assertNotIn("Cargo.lock", rel_paths)

    def test_compute_manifest_round_trip(self) -> None:
        corpus = corpus_for_skeleton(self.root)
        manifest_a = compute_manifest(corpus)
        self.assertIn("src/main.py", manifest_a)
        # Same files → matching manifests.
        self.assertTrue(manifests_match(manifest_a, compute_manifest(corpus)))
        # Modify one file → manifests differ.
        (self.root / "src" / "main.py").write_text(
            "def main():\n    return 1\n", encoding="utf-8"
        )
        manifest_b = compute_manifest(corpus_for_skeleton(self.root))
        self.assertFalse(manifests_match(manifest_a, manifest_b))


class WrapperCorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "ticket_api").mkdir()
        (self.root / "ticket_api" / "models.py").write_text(
            "class Ticket: pass\n", encoding="utf-8"
        )
        (self.root / "web_ui").mkdir()
        (self.root / "web_ui" / "App.tsx").write_text(
            "export const App = () => null;\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_excludes_one_service(self) -> None:
        corpus = corpus_for_wrapper(self.root, exclude_slug="ticket_api")
        rel = sorted(str(p.relative_to(corpus.root)) for p in corpus.files)
        self.assertIn("web_ui/App.tsx", rel)
        self.assertNotIn("ticket_api/models.py", rel)


if __name__ == "__main__":
    unittest.main()
