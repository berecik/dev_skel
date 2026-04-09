"""Corpus discovery for the RAG agent.

A *corpus* is a list of source files that share a logical scope:

* a **skeleton corpus** = every source file under ``_skels/<name>/``;
* a **wrapper corpus** = every sibling service in a generated wrapper
  (used by the integration phase so the agent can ground sibling-client
  code in real signatures rather than guesses).

The same skip-list as :func:`skel_ai_lib.discover_siblings` applies so
the FAISS index never picks up build artefacts.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# --------------------------------------------------------------------------- #
#  Skip lists
# --------------------------------------------------------------------------- #


# Directory names that should never enter the index. Mirrors the skip set
# used by ``skel_ai_lib.discover_siblings`` plus a few build / cache
# directories the chunker has nothing useful to say about.
SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "_shared",
        "_test_projects",
        "node_modules",
        "target",
        "dist",
        "build",
        ".venv",
        "venv",
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".cache",
        ".idea",
        ".vscode",
        ".skel_rag_index",
    }
)


# File extensions worth indexing. Anything outside this set is ignored
# entirely so the embedder doesn't waste cycles on lockfiles, lockbinaries,
# or generated assets. Keep in sync with ``chunker._EXT_TO_LANG`` plus a
# handful of plain-text formats we want retrievable for context.
INDEXABLE_EXTS: frozenset[str] = frozenset(
    {
        # Code (matches chunker)
        ".py",
        ".java",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".rs",
        ".go",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".cs",
        # Docs / config retained for retrieval context
        ".md",
        ".rst",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".cfg",
        ".ini",
        ".sql",
        ".sh",
        ".env",
        ".properties",
        ".gradle",
        ".xml",
    }
)


# Hard cap per file. The chunker truncates oversized chunks too, but the
# corpus walker also drops files that exceed this size to keep the index
# build cheap (mostly relevant when a generated dist/ leaks past the skip
# list).
MAX_FILE_BYTES = 256 * 1024  # 256 KiB


# --------------------------------------------------------------------------- #
#  Corpus dataclass
# --------------------------------------------------------------------------- #


@dataclass
class Corpus:
    """A logical bundle of source files indexable as one FAISS store."""

    id: str
    root: Path
    files: List[Path] = field(default_factory=list)

    def relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(path)


# --------------------------------------------------------------------------- #
#  Public discovery helpers
# --------------------------------------------------------------------------- #


def corpus_for_skeleton(skeleton_path: Path) -> Corpus:
    """Build a corpus over a single skeleton directory.

    Used at per-target generation time so the agent can retrieve
    relevant snippets from the skeleton's reference templates instead
    of stuffing the full ``app/example_items/...`` files into the
    prompt.
    """

    skeleton_path = skeleton_path.resolve()
    files = list(_walk(skeleton_path, exclude_subdirs=()))
    return Corpus(
        id=f"skel:{skeleton_path.name}",
        root=skeleton_path,
        files=files,
    )


def corpus_for_wrapper(
    wrapper_root: Path, *, exclude_slug: Optional[str] = None
) -> Corpus:
    """Build a corpus over every sibling service in a wrapper.

    The freshly generated service (``exclude_slug``) is left out so the
    integration prompts retrieve **only** code from the rest of the
    wrapper. Files outside any service directory (the wrapper-shared
    ``.env``, ``services``, top-level ``README.md`` etc.) are still
    indexed because the integration agent often needs them too.
    """

    wrapper_root = wrapper_root.resolve()
    excluded: Tuple[str, ...] = (exclude_slug,) if exclude_slug else ()
    files = list(_walk(wrapper_root, exclude_subdirs=excluded))
    return Corpus(
        id=f"wrapper:{wrapper_root.name}",
        root=wrapper_root,
        files=files,
    )


# --------------------------------------------------------------------------- #
#  Manifest (mtime + size + sha256[:16]) for cache invalidation
# --------------------------------------------------------------------------- #


def compute_manifest(corpus: Corpus) -> Dict[str, Dict[str, object]]:
    """Return ``{rel_path: {mtime, size, sha}}`` for cache invalidation.

    The vector store helper compares this against the manifest on disk
    to decide whether the cached FAISS index is still valid; any drift
    triggers a rebuild. We hash the **first 16 hex chars** of the file's
    sha256 because the embedding step doesn't actually need a
    cryptographic digest — we only need a quick collision-resistant
    fingerprint.
    """

    out: Dict[str, Dict[str, object]] = {}
    for path in corpus.files:
        try:
            stat = path.stat()
        except OSError:
            continue
        rel = corpus.relative(path)
        out[rel] = {
            "mtime": int(stat.st_mtime),
            "size": stat.st_size,
            "sha": _short_sha256(path),
        }
    return out


def manifests_match(
    a: Dict[str, Dict[str, object]], b: Dict[str, Dict[str, object]]
) -> bool:
    """Cheap structural equality check for two corpus manifests."""

    if a.keys() != b.keys():
        return False
    for key in a:
        if a[key] != b[key]:
            return False
    return True


# --------------------------------------------------------------------------- #
#  Internal walk
# --------------------------------------------------------------------------- #


def _walk(
    root: Path, *, exclude_subdirs: Iterable[str]
) -> Iterable[Path]:
    """Yield indexable files under *root* in a deterministic order."""

    if not root.is_dir():
        return iter(())

    excluded = frozenset(exclude_subdirs)
    out: List[Path] = []
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        # Skip anything inside an excluded subdir or one of the global
        # skip directories.  Walking with rglob is simpler than DFS and
        # the corpora are small enough that the cost is negligible.
        try:
            rel_parts = entry.resolve().relative_to(root.resolve()).parts
        except ValueError:
            continue
        if not rel_parts:
            continue
        if any(part in SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        if excluded and rel_parts[0] in excluded:
            continue
        if entry.suffix.lower() not in INDEXABLE_EXTS:
            continue
        try:
            if entry.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        out.append(entry)
    return out


def _short_sha256(path: Path) -> str:
    """Return the first 16 hex chars of the sha256 of *path*."""

    hasher = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                hasher.update(block)
    except OSError:
        return ""
    return hasher.hexdigest()[:16]
