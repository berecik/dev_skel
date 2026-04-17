"""dev_skel ./ai runtime — service-local AI code refactoring.

Implements the design in ``SERVICE_REFACTOR_COMMAND.md``. This file is
the canonical source of truth; a copy is materialised at
``_skels/_common/refactor_runtime/dev_skel_refactor_runtime.py`` and
shipped into every generated service as ``.ai_runtime.py`` so
the per-service ``./ai`` script keeps working when the service
is detached from a dev_skel checkout.

Two activation modes (see § 3 of the design doc):

* **In-tree** — dev_skel checkout is reachable. Imports
  :class:`skel_rag.agent.RagAgent` and the existing
  :func:`skel_ai_lib.run_test_and_fix_loop` so the LLM call stack
  matches ``skel-gen-ai`` / ``skel-backport``.
* **Out-of-tree** — stdlib-only retrieval (ripgrep with a pathlib
  fallback) plus a bundled minimal fix-loop. No external imports
  beyond the Python stdlib + a single ``urllib.request`` call to
  Ollama.

Public surface (the CLI entrypoint and the data classes both modes
emit):

* :func:`main` — CLI dispatch (``propose`` / ``apply`` / ``verify`` /
  ``explain`` / ``history`` / ``undo``)
* :class:`RefactorContext`, :class:`FileEdit`, :class:`AppliedResult`
* :func:`detect_devskel`, :func:`build_runner`
* :class:`RagRunner`, :class:`MinimalRunner` — both implement the
  same Protocol surface
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

__all__ = [
    "RefactorContext",
    "FileEdit",
    "AppliedResult",
    "RagRunner",
    "MinimalRunner",
    "RefactorAbort",
    "RefactorParseError",
    "RefactorOllamaError",
    "detect_devskel",
    "build_runner",
    "main",
]


# --------------------------------------------------------------------------- #
#  Data classes + exceptions
# --------------------------------------------------------------------------- #


class RefactorAbort(RuntimeError):
    """Raised when an apply precondition is not met (clean tree, lock, ...)."""


class RefactorParseError(ValueError):
    """Raised when an LLM response cannot be split into FileEdits."""


class RefactorOllamaError(RuntimeError):
    """Raised when Ollama is unreachable / returns an error."""


@dataclass
class FileEdit:
    """One file's worth of refactor edit, produced by the LLM."""

    rel_path: str
    language: str
    new_contents: str
    rationale: str = ""
    is_new_file: bool = False


@dataclass
class AppliedResult:
    """Result of :func:`_apply_edits_with_stash`."""

    written: List[Path] = field(default_factory=list)
    skipped: List[Tuple[Path, str]] = field(default_factory=list)
    stash_ref: Optional[str] = None
    snapshot_ref: Optional[str] = None


@dataclass
class RefactorContext:
    """Per-run inputs collected by the CLI."""

    service_dir: Path
    request: str
    sidecar: Optional[Dict[str, Any]] = None
    mode: str = "out-of-tree"
    devskel_root: Optional[Path] = None
    include_siblings: bool = False
    include_skeleton: bool = True
    max_files: int = 8
    test_command: str = "./test"
    fix_timeout_m: int = 15
    allow_dirty: bool = False
    no_verify: bool = False
    no_llm: bool = False
    output_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
        sha = hashlib.sha256(self.request.encode("utf-8")).hexdigest()[:6]
        run_name = f"{ts}-{sha}"
        candidate = self.service_dir / ".ai" / run_name
        suffix = 0
        while candidate.exists():
            suffix += 1
            candidate = self.service_dir / ".ai" / f"{run_name}.{suffix}"
        self.output_dir = candidate


@dataclass
class _TestRunResult:
    """Stdlib-only mirror of :class:`skel_ai_lib.TestRunResult`."""

    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_s: float

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    def combined_output(self, max_chars: int = 6000) -> str:
        body = (self.stdout or "") + ("\n" + self.stderr if self.stderr else "")
        if len(body) > max_chars:
            return body[-max_chars:]
        return body


# --------------------------------------------------------------------------- #
#  dev_skel detection
# --------------------------------------------------------------------------- #


def _looks_like_devskel(p: Path) -> bool:
    return (
        p.is_dir()
        and (p / "_skels").is_dir()
        and (p / "_bin" / "skel-gen-ai").is_file()
        and (p / "_skels" / "_common").is_dir()
    )


def detect_devskel(service_dir: Path) -> Optional[Path]:
    """Return the dev_skel root or None — see § 3.1 of the design doc."""

    env = os.environ.get("DEV_SKEL_ROOT", "").strip()
    if env:
        candidate = Path(env).expanduser().resolve()
        if _looks_like_devskel(candidate):
            return candidate
        raise RefactorAbort(
            f"DEV_SKEL_ROOT={env!r} does not look like a dev_skel checkout "
            "(missing _bin/skel-gen-ai or _skels/)."
        )

    sidecar = service_dir / ".skel_context.json"
    if sidecar.is_file():
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            rel = payload.get("skeleton_path_rel")
            if rel:
                cur = service_dir.parent
                for _ in range(8):
                    candidate = (cur / rel).resolve()
                    devskel_root = candidate.parent.parent
                    if _looks_like_devskel(devskel_root):
                        return devskel_root
                    cur = cur.parent
        except (OSError, json.JSONDecodeError):
            pass

    for start in (service_dir, Path.cwd()):
        cur = start.resolve()
        for _ in range(10):
            if _looks_like_devskel(cur):
                return cur
            if cur == cur.parent:
                break
            cur = cur.parent

    for p in (
        Path.home() / "dev_skel",
        Path.home() / "src" / "dev_skel",
        Path("/opt/dev_skel"),
        Path("/usr/local/share/dev_skel"),
    ):
        if _looks_like_devskel(p):
            return p

    return None


def _load_sidecar(service_dir: Path) -> Optional[Dict[str, Any]]:
    sidecar = service_dir / ".skel_context.json"
    if not sidecar.is_file():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# --------------------------------------------------------------------------- #
#  Project-wide AI memory
# --------------------------------------------------------------------------- #
#
# Each ``./ai apply`` appends a single JSONL line to two files:
#
#   <service>/.ai/memory.jsonl     — per-service history
#   <wrapper>/.ai/memory.jsonl     — project-wide history (shared
#                                     across every service in the
#                                     wrapper)
#
# Every subsequent ``./ai propose`` reads the last K entries from the
# wrapper-shared memory and prepends them to the LLM's user prompt as
# a "PREVIOUS_AI_RUNS" block. The model gains continuity across
# invocations: it knows the user just renamed `Item` → `Task`, that
# the previous test fixture was `pagination`, etc. — and can avoid
# re-doing or undoing prior work.
#
# Storage format is JSONL so:
#   * appends are atomic (single line per write),
#   * cross-service reads stream cheaply (no JSON-parse-the-world),
#   * the file is human-greppable (`grep "extract auth"
#     <wrapper>/.ai/memory.jsonl`).
#
# An entry looks like::
#
#   {
#     "ts": "2026-04-16T18:03:21Z",
#     "service": "items_api",
#     "request": "extract a service layer ...",
#     "edited_files": ["app/items/service.py", ...],
#     "rationale": "<truncated to 800 chars>",
#     "passed": true,
#     "fix_loop_iterations": 0
#   }


_MEMORY_FILE_NAME = "memory.jsonl"
# Cap how many bytes of rationale we persist per entry. 800 chars is
# enough for a few sentences (the model's per-file rationale paragraph)
# without the JSONL file ballooning past a megabyte over hundreds of
# runs.
_MEMORY_RATIONALE_CHARS = 800
# Default number of recent entries surfaced into the prompt. 5 is a
# sweet spot between "enough context to be useful" and "small enough
# to not eat the model's context window".
_MEMORY_PROMPT_LIMIT = 5


def _wrapper_dir(service_dir: Path) -> Path:
    """Return the wrapper directory (parent of the service)."""

    return service_dir.parent


def _memory_paths(service_dir: Path) -> List[Path]:
    """Return ``[wrapper_memory, service_memory]`` (priority order).

    Order matters for *reads*: callers walk this list in order and
    stop at the first existing file when they want a single source
    (e.g. when surfacing into the prompt we prefer wrapper memory
    because it carries cross-service context). For *writes* we
    append to BOTH so a per-service ``history`` view stays useful
    even when the wrapper memory was deleted.
    """

    return [
        _wrapper_dir(service_dir) / ".ai" / _MEMORY_FILE_NAME,
        service_dir / ".ai" / _MEMORY_FILE_NAME,
    ]


def _append_memory(path: Path, entry: Dict[str, Any]) -> None:
    """Append one JSONL line. Best-effort — never raises on IO error."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        # Memory is a UX nicety — a flaky disk shouldn't break apply.
        pass


def _load_recent_memory(
    path: Path, *, limit: int = _MEMORY_PROMPT_LIMIT,
) -> List[Dict[str, Any]]:
    """Read the last ``limit`` valid JSONL entries from ``path``.

    Skips malformed lines silently — a corrupt entry from an older
    runtime version cannot poison new prompts.
    """

    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in lines[-limit * 2:]:  # over-fetch so we keep `limit` valid ones
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-limit:]


def _format_memory_block(entries: List[Dict[str, Any]]) -> str:
    """Render memory entries as a Markdown block for the LLM prompt.

    Returns the empty string when there are no entries (callers can
    drop the prompt section entirely instead of emitting "(no
    memory)" noise).
    """

    if not entries:
        return ""
    lines = [
        "## PREVIOUS_AI_RUNS",
        "",
        "Recent ./ai runs in this project (newest first). Use them as "
        "context — do not redo work that already landed; do not undo "
        "work that already landed. If the new request CONFLICTS with a "
        "prior run, call it out in your RATIONALE rather than silently "
        "reverting the previous edit.",
        "",
    ]
    for entry in reversed(entries):
        ts = entry.get("ts", "")
        svc = entry.get("service", "?")
        req = entry.get("request", "(no request recorded)")
        files = entry.get("edited_files") or []
        passed = entry.get("passed")
        status = "PASS" if passed else "FAIL" if passed is False else "?"
        lines.append(f"- **[{ts}] {svc} ({status})** — {req}")
        for f in files[:8]:
            lines.append(f"    - {f}")
        rationale = entry.get("rationale") or ""
        if rationale:
            head = rationale.strip().splitlines()[0]
            lines.append(f"    rationale: {head[:200]}")
    lines.append("")
    return "\n".join(lines)


def _record_apply_to_memory(
    ctx: "RefactorContext",
    applied: "AppliedResult",
    test_result: Optional["_TestRunResult"],
    rationale_text: str,
) -> None:
    """Append a memory entry to BOTH the wrapper- and per-service log."""

    entry: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": ctx.service_dir.name,
        "request": ctx.request,
        "edited_files": [
            str(p.resolve().relative_to(ctx.service_dir.resolve()))
            for p in applied.written
        ],
        "rationale": (rationale_text or "")[:_MEMORY_RATIONALE_CHARS],
    }
    if test_result is not None:
        entry["passed"] = bool(test_result.passed)
        entry["returncode"] = int(test_result.returncode)
    for path in _memory_paths(ctx.service_dir):
        _append_memory(path, entry)


def _load_project_memory_block(
    service_dir: Path, *, limit: int = _MEMORY_PROMPT_LIMIT,
) -> str:
    """Convenience wrapper used by the propose pipeline."""

    wrapper_path, service_path = _memory_paths(service_dir)
    # Prefer the wrapper-shared file — it carries cross-service
    # context. Fall back to the per-service file when the wrapper
    # log is missing (e.g. user deleted `<wrapper>/.ai/`).
    primary = wrapper_path if wrapper_path.is_file() else service_path
    return _format_memory_block(_load_recent_memory(primary, limit=limit))


# --------------------------------------------------------------------------- #
#  LLM response parser
# --------------------------------------------------------------------------- #


_FILE_HEADER_RE = re.compile(r"^FILE:\s*(?P<path>\S+)\s*$", re.MULTILINE)
_LANG_HEADER_RE = re.compile(r"^LANG:\s*(?P<lang>\S+)\s*$", re.MULTILINE)
_ENDFILE_RE = re.compile(r"^ENDFILE\s*$", re.MULTILINE)
_RATIONALE_RE = re.compile(
    r"RATIONALE:\s*(?P<body>.*?)(?=^(?:FILE:|FILES:))",
    re.DOTALL | re.MULTILINE,
)


_LANGUAGE_BY_EXT = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".jsx": "jsx", ".rs": "rust", ".go": "go",
    ".java": "java", ".kt": "kotlin", ".dart": "dart", ".sql": "sql",
    ".md": "markdown", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".sh": "bash",
}


def _language_for_path(rel: str) -> str:
    return _LANGUAGE_BY_EXT.get(Path(rel).suffix, "text")


def _strip_outer_fence(body: str, *, language: str) -> str:
    pattern = re.compile(
        rf"^\s*```(?:{re.escape(language)}|\w*)?\s*\n(.*?)\n```\s*$",
        re.DOTALL,
    )
    m = pattern.match(body)
    return m.group(1) if m else body


def _extract_per_file_rationale(rationale_block: str, rel_path: str) -> str:
    pat = re.compile(
        rf"^{re.escape(rel_path)}\s*:\s*(?P<body>.+?)(?=^\S+:|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(rationale_block)
    return m.group("body").strip() if m else ""


def _split_refactor_response(
    raw: str, *, max_files: int,
) -> List[FileEdit]:
    """Parse FILE/LANG/ENDFILE blocks from an LLM response.

    Tolerates extra whitespace, markdown fences inside the body, an
    optional RATIONALE paragraph, and an optional ``FILES: <n>``
    declaration. Rejects path-traversal, duplicate paths, more than
    ``max_files`` blocks, and empty bodies.
    """

    if not raw or not raw.strip():
        raise RefactorParseError("empty LLM response")

    rationale_match = _RATIONALE_RE.search(raw)
    rationale_block = (
        rationale_match.group("body").strip() if rationale_match else ""
    )

    headers = list(_FILE_HEADER_RE.finditer(raw))
    if not headers:
        raise RefactorParseError(
            "no FILE: blocks found — model produced free-form text"
        )

    if len(headers) > max_files:
        raise RefactorParseError(
            f"model emitted {len(headers)} FILE blocks; cap is {max_files}"
        )

    edits: List[FileEdit] = []
    seen_paths: Set[str] = set()
    for i, header in enumerate(headers):
        rel_path = header.group("path")

        if rel_path.startswith("/") or rel_path.startswith("./"):
            raise RefactorParseError(
                f"FILE: {rel_path!r} has leading slash or ./ — refusing"
            )
        if Path(rel_path).is_absolute() or ".." in Path(rel_path).parts:
            raise RefactorParseError(
                f"FILE: {rel_path!r} escapes service directory"
            )
        if rel_path in seen_paths:
            raise RefactorParseError(
                f"FILE: {rel_path!r} appeared more than once"
            )
        seen_paths.add(rel_path)

        body_start = header.end()
        next_header_start = (
            headers[i + 1].start() if i + 1 < len(headers) else len(raw)
        )
        chunk = raw[body_start:next_header_start]

        chunk_stripped = chunk.lstrip("\n")
        lang_m = _LANG_HEADER_RE.match(chunk_stripped)
        if lang_m:
            language = lang_m.group("lang")
            offset = len(chunk) - len(chunk_stripped) + lang_m.end()
            chunk = chunk[offset:]
        else:
            language = _language_for_path(rel_path)

        end_m = _ENDFILE_RE.search(chunk)
        if not end_m:
            raise RefactorParseError(
                f"FILE: {rel_path!r} missing ENDFILE sentinel"
            )
        body = chunk[: end_m.start()].strip("\n")
        body = _strip_outer_fence(body, language=language)
        body = body.replace("\r\n", "\n")

        if not body.strip():
            raise RefactorParseError(
                f"FILE: {rel_path!r} body is empty"
            )

        edits.append(
            FileEdit(
                rel_path=rel_path,
                language=language,
                new_contents=body + "\n",
                rationale=_extract_per_file_rationale(rationale_block, rel_path),
                is_new_file=False,
            )
        )

    return edits


# --------------------------------------------------------------------------- #
#  Git helpers
# --------------------------------------------------------------------------- #


_STASH_MESSAGE = "skel-ai pre-apply"
_DEFAULT_DENYLIST = {
    ".git", ".venv", "node_modules", ".ai",
    "refactor", ".ai_runtime.py",
}


def _git(*args: str, cwd: Path, check: bool = True,
         capture: bool = False) -> str:
    res = subprocess.run(
        ("git",) + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )
    return res.stdout if capture else ""


def _has_git(path: Path) -> bool:
    try:
        _git("rev-parse", "--is-inside-work-tree", cwd=path, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _has_uncommitted_changes(path: Path) -> bool:
    try:
        out = _git(
            "status", "--porcelain", "--untracked-files=normal",
            cwd=path, capture=True,
        )
    except subprocess.CalledProcessError:
        return False
    return bool(out.strip())


def _has_existing_refactor_stash(path: Path) -> bool:
    try:
        out = _git("stash", "list", cwd=path, capture=True)
    except subprocess.CalledProcessError:
        return False
    return any(_STASH_MESSAGE in line for line in out.splitlines())


def _git_first_stash_ref(path: Path) -> Optional[str]:
    try:
        out = _git("stash", "list", "-1", cwd=path, capture=True)
    except subprocess.CalledProcessError:
        return None
    m = re.match(r"^(stash@\{\d+\}):", out.strip())
    return m.group(1) if m else None


def _under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
#  Apply / rollback
# --------------------------------------------------------------------------- #


def _apply_edits_with_stash(
    ctx: RefactorContext,
    edits: List[FileEdit],
    *,
    progress: Any = None,
) -> AppliedResult:
    """Snapshot, write, return — caller invokes verify, then drops/pops."""

    service_dir = ctx.service_dir.resolve()

    if _has_existing_refactor_stash(service_dir):
        raise RefactorAbort(
            f"A previous ./ai apply left an unpopped stash named "
            f"'{_STASH_MESSAGE}'. Run `git stash list`, then drop it manually."
        )

    if _has_git(service_dir) and _has_uncommitted_changes(service_dir):
        if not ctx.allow_dirty:
            raise RefactorAbort(
                "Service has uncommitted changes. Commit them or pass "
                "--allow-dirty (rollback may then fail to fully restore)."
            )

    lock_path = ctx.service_dir / ".ai" / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(
            lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600,
        )
    except FileExistsError:
        raise RefactorAbort(
            f"Another ./ai apply is in progress (lock file "
            f"{lock_path}). If you are sure no other process is "
            "running, delete it manually."
        )
    os.write(lock_fd, str(os.getpid()).encode())
    os.close(lock_fd)

    stash_ref: Optional[str] = None
    snapshot_ref: Optional[str] = None
    written: List[Path] = []
    skipped: List[Tuple[Path, str]] = []

    try:
        if _has_git(service_dir):
            try:
                _git(
                    "stash", "push",
                    "--include-untracked", "--keep-index",
                    "--message", _STASH_MESSAGE,
                    cwd=service_dir,
                )
                stash_ref = _git_first_stash_ref(service_dir)
                snap_out = subprocess.run(
                    ("git", "stash", "create"),
                    cwd=str(service_dir), capture_output=True, text=True,
                )
                if snap_out.returncode == 0 and snap_out.stdout.strip():
                    snapshot_ref = snap_out.stdout.strip()
            except subprocess.CalledProcessError:
                stash_ref = None
        elif progress is not None:
            progress.write(
                f"[ai] WARN: {service_dir} is not in a git repo — "
                "rollback unavailable. `git init && git add . && git commit "
                "-m baseline` to enable.\n"
            )

        for edit in edits:
            target = (service_dir / edit.rel_path).resolve()
            if not _under(target, service_dir):
                skipped.append((target, "outside service directory"))
                continue
            try:
                rel_parts = set(target.relative_to(service_dir).parts)
            except ValueError:
                skipped.append((target, "outside service directory"))
                continue
            if rel_parts & _DEFAULT_DENYLIST:
                skipped.append((target, "protected path"))
                continue
            if target.is_symlink():
                skipped.append((target, "refusing to follow symlink"))
                continue
            if target.exists() and not target.is_file():
                skipped.append((target, "not a regular file"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            edit.is_new_file = not target.exists()
            target.write_text(edit.new_contents, encoding="utf-8")
            written.append(target)
            if progress is not None:
                marker = "A" if edit.is_new_file else "M"
                progress.write(f"[ai] {marker}  {edit.rel_path}\n")

        return AppliedResult(
            written=written, skipped=skipped,
            stash_ref=stash_ref, snapshot_ref=snapshot_ref,
        )
    except Exception:
        if stash_ref:
            with contextlib.suppress(subprocess.CalledProcessError):
                _git("stash", "pop", "--quiet", stash_ref, cwd=service_dir)
        raise
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(lock_path)


def _rollback(ctx: RefactorContext, applied: AppliedResult) -> None:
    if applied.stash_ref:
        with contextlib.suppress(subprocess.CalledProcessError):
            _git(
                "stash", "pop", "--quiet", applied.stash_ref,
                cwd=ctx.service_dir,
            )


def _drop_stash(ctx: RefactorContext, applied: AppliedResult) -> None:
    if applied.stash_ref:
        with contextlib.suppress(subprocess.CalledProcessError):
            _git(
                "stash", "drop", "--quiet", applied.stash_ref,
                cwd=ctx.service_dir,
            )


# --------------------------------------------------------------------------- #
#  Out-of-tree retrieval (ripgrep / pathlib)
# --------------------------------------------------------------------------- #


_STOPWORDS = frozenset({
    "a", "an", "and", "for", "from", "in", "into", "of", "on",
    "or", "the", "to", "with", "this", "that", "is", "are", "be",
    "do", "does", "by", "as", "at", "make", "use", "using", "add",
    "remove", "change", "update", "fix", "extract", "rename",
    "service", "code",
})

_INDEXABLE_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java",
    ".kt", ".dart", ".sql", ".sh", ".yaml", ".yml", ".json",
    ".md", ".toml",
}


def _tokenise(s: str) -> List[str]:
    raw = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", s.lower())
    return [t for t in raw if t not in _STOPWORDS]


def _is_indexable(p: Path) -> bool:
    if not p.is_file():
        return False
    if any(part in _DEFAULT_DENYLIST for part in p.parts):
        return False
    try:
        if p.stat().st_size > 256 * 1024:
            return False
    except OSError:
        return False
    return p.suffix in _INDEXABLE_EXT


def _select_files_via_grep(
    service_dir: Path, request: str, max_files: int,
) -> List[Path]:
    tokens = _tokenise(request)
    if not tokens:
        return []
    have_rg = shutil.which("rg") is not None
    scores: collections.Counter = collections.Counter()
    for token in tokens:
        if have_rg:
            try:
                out = subprocess.run(
                    [
                        "rg", "-l", "--hidden", "--no-ignore-vcs",
                        "-i", token, str(service_dir),
                    ],
                    capture_output=True, text=True, timeout=20,
                )
            except (subprocess.TimeoutExpired, OSError):
                continue
            for line in out.stdout.splitlines():
                p = Path(line)
                if _is_indexable(p):
                    scores[p] += 3
        else:
            for p in service_dir.rglob("*"):
                if not _is_indexable(p):
                    continue
                try:
                    if token in p.read_text(
                        encoding="utf-8", errors="ignore",
                    ).lower():
                        scores[p] += 2
                except OSError:
                    continue

    now = time.time()
    for p in list(scores):
        try:
            age_days = (now - p.stat().st_mtime) / 86400
            scores[p] += max(0, int(5 - age_days))
        except OSError:
            pass

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return [p for p, _ in ranked[:max_files]]


def _render_files_block(
    paths: List[Path], service_dir: Path, *, max_per_file: int = 4096,
) -> str:
    parts: List[str] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > max_per_file:
            text = text[:max_per_file] + "\n... (truncated)\n"
        rel = p.relative_to(service_dir).as_posix()
        lang = _language_for_path(rel)
        parts.append(f"## {rel}\n\n```{lang}\n{text}\n```\n")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
#  Out-of-tree LLM call
# --------------------------------------------------------------------------- #


REFACTOR_SYSTEM_PROMPT_MIN = (
    "You are a senior engineer refactoring code in a single service.\n"
    "You will receive a free-form REQUEST and a RETRIEVED_CONTEXT block "
    "containing the most relevant files from the service.\n"
    "\n"
    "Your job:\n"
    "  1. Decide the minimal set of files to edit (cap: {max_files}).\n"
    "  2. For each file, output the FULL new contents (no patches).\n"
    "  3. Preserve every public API the service exposes UNLESS the "
    "     request explicitly changes it.\n"
    "  4. Never reference paths outside the service directory.\n"
    "  5. Never invent third-party imports the service does not "
    "     already use; if the request implies a new dep, name it in "
    "     RATIONALE so the developer can install it.\n"
    "\n"
    "Output format (STRICT — the parser is regex-based):\n"
    "RATIONALE:\n"
    "<one short paragraph per file you edit, prefixed `path:`>\n"
    "\n"
    "FILES: <number of files you produce>\n"
    "\n"
    "FILE: <relative path 1>\n"
    "LANG: <language tag>\n"
    "<full contents>\n"
    "ENDFILE\n"
    "\n"
    "Repeat the FILE/LANG/ENDFILE pattern for each file. Do not emit "
    "anything outside the block. Do not include diff markers (no "
    "leading +/-)."
)


REFACTOR_FIX_SYSTEM_PROMPT_MIN = (
    "You are repairing the most recent refactor. Re-emit FILE blocks "
    "(only for files listed in PREVIOUS_REFACTOR_FILES) so the failing "
    "test command passes. Do not edit any file not listed."
)


def _ollama_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """Stdlib-only POST to Ollama's OpenAI-compatible chat endpoint."""

    model = model or os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")
    base_url = (base_url or os.environ.get(
        "OLLAMA_BASE_URL", "http://localhost:11434",
    )).rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    timeout = timeout if timeout is not None else int(
        os.environ.get("OLLAMA_TIMEOUT", "1800"),
    )
    temperature = temperature if temperature is not None else float(
        os.environ.get("OLLAMA_TEMPERATURE", "0.2"),
    )

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": temperature,
    }).encode("utf-8")

    url = base_url + "/v1/chat/completions"
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_excerpt = ""
        try:
            body_excerpt = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RefactorOllamaError(
            f"Ollama HTTP {exc.code} from {url}: {body_excerpt}",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RefactorOllamaError(
            f"Could not reach Ollama at {url}: {exc}",
        ) from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RefactorOllamaError(
            f"Malformed Ollama response from {url}: {exc!r}",
        ) from exc


# --------------------------------------------------------------------------- #
#  Test running + minimal fix loop
# --------------------------------------------------------------------------- #


def _run_test(ctx: RefactorContext) -> _TestRunResult:
    cmd = shlex.split(ctx.test_command)
    if not cmd:
        raise RefactorAbort(f"empty test command: {ctx.test_command!r}")
    if cmd[0].startswith("./"):
        cmd[0] = str((ctx.service_dir / cmd[0][2:]).resolve())
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ctx.service_dir),
            capture_output=True,
            text=True,
            timeout=ctx.fix_timeout_m * 60,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else (
            (exc.stdout or b"").decode("utf-8", errors="replace")
        )
        err_extra = exc.stderr if isinstance(exc.stderr, str) else (
            (exc.stderr or b"").decode("utf-8", errors="replace")
        )
        return _TestRunResult(
            command=" ".join(cmd),
            cwd=str(ctx.service_dir),
            returncode=-1,
            stdout=out or "",
            stderr=(err_extra or "") + "\n[ai] test timed out",
            duration_s=time.monotonic() - start,
        )
    except FileNotFoundError as exc:
        return _TestRunResult(
            command=" ".join(cmd),
            cwd=str(ctx.service_dir),
            returncode=127,
            stdout="",
            stderr=f"test runner not found: {exc}",
            duration_s=time.monotonic() - start,
        )
    return _TestRunResult(
        command=" ".join(cmd),
        cwd=str(ctx.service_dir),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=time.monotonic() - start,
    )


def _minimal_fix_loop(
    ctx: RefactorContext,
    applied: AppliedResult,
    *,
    progress: Any = None,
) -> _TestRunResult:
    """≤100-line minimal loop, files-restricted."""

    deadline = time.monotonic() + ctx.fix_timeout_m * 60
    iteration = 0
    last = _run_test(ctx)
    if progress is not None:
        status = "PASS" if last.passed else f"FAIL (exit {last.returncode})"
        progress.write(f"[ai] {status} in {last.duration_s:.1f}s\n")

    allowed = {
        p.relative_to(ctx.service_dir.resolve()).as_posix()
        for p in applied.written
    }

    while not last.passed and time.monotonic() < deadline:
        iteration += 1
        files_block = _render_files_block(applied.written, ctx.service_dir)
        prompt_user = (
            f"REQUEST: repair the most recent refactor so the test "
            f"command `{ctx.test_command}` passes.\n\n"
            f"PREVIOUS_REFACTOR_FILES (only edit files in this list):\n"
            f"{sorted(allowed)}\n\n"
            f"FILES_BODY:\n{files_block}\n\n"
            f"FAILING_TEST_OUTPUT (returncode={last.returncode}):\n"
            f"{last.combined_output(max_chars=6000)}\n\n"
            f"Output FILE/LANG/ENDFILE blocks (max {len(applied.written)})."
        )
        try:
            raw = _ollama_chat(REFACTOR_FIX_SYSTEM_PROMPT_MIN, prompt_user)
        except RefactorOllamaError as exc:
            if progress is not None:
                progress.write(f"[ai] fix loop: Ollama error — {exc}\n")
            break

        try:
            patches = _split_refactor_response(
                raw, max_files=len(applied.written),
            )
        except RefactorParseError as exc:
            if progress is not None:
                progress.write(f"[ai] fix loop: parse error — {exc}\n")
            break

        applied_count = 0
        for p in patches:
            if p.rel_path not in allowed:
                if progress is not None:
                    progress.write(
                        f"[ai] fix loop: skipping {p.rel_path} "
                        "(not in original edit set)\n"
                    )
                continue
            (ctx.service_dir / p.rel_path).write_text(
                p.new_contents, encoding="utf-8",
            )
            applied_count += 1
            if progress is not None:
                progress.write(
                    f"[ai] Refactor fix pass {iteration}/?: "
                    f"patched {p.rel_path}\n"
                )
        if applied_count == 0:
            break
        last = _run_test(ctx)
        if progress is not None:
            status = "PASS" if last.passed else f"FAIL (exit {last.returncode})"
            progress.write(
                f"[ai] {status} in {last.duration_s:.1f}s "
                f"(iter {iteration})\n"
            )

    return last


# --------------------------------------------------------------------------- #
#  Runner abstractions
# --------------------------------------------------------------------------- #


class MinimalRunner:
    """Out-of-tree runner. Stdlib + Ollama HTTP only."""

    name = "out-of-tree"
    rag_label = "minimal-grep"

    def __init__(self, ctx: RefactorContext, *, progress: Any = None) -> None:
        self.ctx = ctx
        self.progress = progress

    def retrieve(self) -> str:
        files = _select_files_via_grep(
            self.ctx.service_dir, self.ctx.request, self.ctx.max_files,
        )
        if self.progress is not None:
            label = "ripgrep" if shutil.which("rg") else "pathlib"
            self.progress.write(
                f"[ai] Retrieving context "
                f"({len(files)} files via {label})\n"
            )
        return _render_files_block(files, self.ctx.service_dir)

    def propose(self, retrieved: str) -> List[FileEdit]:
        if self.ctx.no_llm:
            return []
        sidecar = self.ctx.sidecar or {}
        memory_block = _load_project_memory_block(self.ctx.service_dir)
        prompt_user = (
            f"REQUEST: {self.ctx.request}\n\n"
            f"GENERATION_CONTEXT:\n"
            f"  service_label: {sidecar.get('service_label', '?')}\n"
            f"  service_slug:  {sidecar.get('service_slug', self.ctx.service_dir.name)}\n"
            f"  item_class:    {sidecar.get('item_class', '?')}\n"
            f"  auth_type:     {sidecar.get('auth_type', '?')}\n"
            f"\n"
            f"Hard cap: edit at most {self.ctx.max_files} files.\n"
            + (f"\n{memory_block}\n" if memory_block else "")
            + f"\nRETRIEVED_CONTEXT:\n{retrieved}\n\n"
            f"Now produce RATIONALE / FILES / FILE blocks as instructed."
        )
        if self.progress is not None:
            model = os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")
            base_url = os.environ.get(
                "OLLAMA_BASE_URL", "http://localhost:11434",
            )
            self.progress.write(
                f"[ai] Asking Ollama ({model} @ {base_url})...\n"
            )
        raw = _ollama_chat(
            REFACTOR_SYSTEM_PROMPT_MIN.format(max_files=self.ctx.max_files),
            prompt_user,
        )
        return _split_refactor_response(raw, max_files=self.ctx.max_files)

    def apply(self, edits: List[FileEdit]) -> AppliedResult:
        return _apply_edits_with_stash(self.ctx, edits, progress=self.progress)

    def verify(self, applied: AppliedResult) -> _TestRunResult:
        return _minimal_fix_loop(self.ctx, applied, progress=self.progress)


class RagRunner:
    """In-tree runner. Imports skel_rag.agent.RagAgent."""

    name = "in-tree"
    rag_label = "full"

    def __init__(self, ctx: RefactorContext, *, progress: Any = None) -> None:
        if ctx.devskel_root is None:
            raise RefactorAbort("RagRunner requires ctx.devskel_root")
        sys.path.insert(0, str(ctx.devskel_root / "_bin"))
        self.ctx = ctx
        self.progress = progress
        self._agent: Optional[Any] = None

    @property
    def agent(self) -> Any:
        if self._agent is None:
            try:
                from skel_rag.agent import RagAgent
                from skel_rag.config import OllamaConfig
            except ImportError as exc:
                raise RefactorAbort(
                    "in-tree mode requires skel_rag deps "
                    "(`make install-rag-deps`): " + str(exc),
                ) from exc
            self._agent = RagAgent(ollama_cfg=OllamaConfig.from_env())
        return self._agent

    def retrieve(self) -> str:
        try:
            from skel_rag.corpus import corpus_for_skeleton
            from skel_rag.prompts import (
                build_query_for_refactor,
                render_retrieved_block,
            )
        except ImportError:
            return MinimalRunner(self.ctx, progress=self.progress).retrieve()
        primary = corpus_for_skeleton(self.ctx.service_dir)
        retriever = self.agent.get_retriever(primary)
        if retriever is None:
            return MinimalRunner(self.ctx, progress=self.progress).retrieve()
        chunks = retriever.retrieve(
            build_query_for_refactor(self.ctx.request, self.ctx.sidecar),
            language=None,
        )
        if self.progress is not None:
            self.progress.write(
                f"[ai] Retrieving context ({len(chunks)} chunks)\n"
            )
        return render_retrieved_block(
            chunks, max_chars=self.agent.rag_cfg.max_context_chars,
        )

    def propose(self, retrieved: str) -> List[FileEdit]:
        if self.ctx.no_llm:
            return []
        # Prepend the project-wide memory block to the retrieved
        # context. The agent prompt embeds `retrieved` verbatim under
        # the `{retrieved_context}` placeholder, so threading memory
        # in here (instead of forking the prompt template) is the
        # least-invasive way to give the model continuity across
        # invocations. An empty memory block adds zero overhead.
        memory_block = _load_project_memory_block(self.ctx.service_dir)
        merged = (
            f"{memory_block}\n\n---\n\n{retrieved}"
            if memory_block else retrieved
        )
        # `RagAgent.refactor_files` only references `ctx.request` and
        # `ctx.service_dir` — both attributes of our RefactorContext —
        # so we can pass `self.ctx` directly without an adapter
        # GenerationContext (which would lack `request` anyway). The
        # AttributeError fallback covers the case where an older
        # skel_rag is on PYTHONPATH and the method has not been added
        # yet; we then fall through to the stdlib MinimalRunner.
        try:
            return self.agent.refactor_files(
                ctx=self.ctx,
                retrieved=merged,
                max_files=self.ctx.max_files,
            )
        except AttributeError:
            return MinimalRunner(self.ctx, progress=self.progress).propose(merged)

    def apply(self, edits: List[FileEdit]) -> AppliedResult:
        return _apply_edits_with_stash(self.ctx, edits, progress=self.progress)

    def verify(self, applied: AppliedResult) -> _TestRunResult:
        try:
            from skel_ai_lib import (
                AiTarget,
                IntegrationManifest,
                TargetResult,
                run_test_and_fix_loop,
            )
        except ImportError:
            return _minimal_fix_loop(self.ctx, applied, progress=self.progress)

        ctx_for_lib = _adapt_sidecar_to_genctx(self.ctx)
        manifest = IntegrationManifest(
            skeleton_name=(self.ctx.sidecar or {}).get("skeleton_name", "unknown"),
            targets=[],
            test_command=self.ctx.test_command,
            fix_timeout_m=self.ctx.fix_timeout_m,
        )
        allowed = [
            str(p.resolve().relative_to(self.ctx.service_dir.resolve()))
            for p in applied.written
        ]

        def _discover(_project_dir: Path) -> List[Any]:
            results: List[Any] = []
            for rel in allowed:
                p = self.ctx.service_dir / rel
                if not p.is_file():
                    continue
                results.append(
                    TargetResult(
                        target=AiTarget(
                            path=rel,
                            template=None,
                            prompt="",
                            language=_language_for_path(rel),
                            description=f"refactor: {rel}",
                        ),
                        written_to=p,
                        bytes_written=p.stat().st_size,
                    ),
                )
            return results

        try:
            return run_test_and_fix_loop(
                client=self.agent,
                ctx=ctx_for_lib,
                manifest=manifest,
                integration_results=[],
                discover_project_files=_discover,
                progress=self.progress,
            )
        except TypeError:
            # Older skel_ai_lib without discover_project_files kwarg.
            return _minimal_fix_loop(
                self.ctx, applied, progress=self.progress,
            )


def _adapt_sidecar_to_genctx(ctx: RefactorContext) -> Any:
    from skel_ai_lib import GenerationContext

    sidecar = ctx.sidecar or {}
    return GenerationContext(
        skeleton_name=sidecar.get("skeleton_name", "refactor"),
        skeleton_path=Path(sidecar.get("skeleton_path", str(ctx.service_dir))),
        project_root=ctx.service_dir.parent,
        project_name=sidecar.get("project_name", ctx.service_dir.parent.name),
        service_subdir=sidecar.get("service_subdir", ctx.service_dir.name),
        service_label=sidecar.get("service_label", ctx.service_dir.name),
        item_name=sidecar.get("item_name", "item"),
        auth_type=sidecar.get("auth_type", "none"),
    )


def build_runner(
    ctx: RefactorContext, *, progress: Any = None,
) -> Any:
    if ctx.mode == "in-tree":
        try:
            return RagRunner(ctx, progress=progress)
        except RefactorAbort:
            ctx.mode = "out-of-tree"
            return MinimalRunner(ctx, progress=progress)
    return MinimalRunner(ctx, progress=progress)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #


_SUBCOMMANDS = {"propose", "apply", "verify", "explain", "history", "undo", "upgrade"}


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="./ai",
        description=(
            "AI-driven refactoring inside a generated dev_skel service. "
            "Run `./ai \"REQUEST\"` for a one-shot dry-run proposal, "
            "`./ai apply \"REQUEST\"` to write files, or `./ai upgrade` "
            "to pull changes from the skeleton."
        ),
    )
    parser.add_argument(
        "subcommand_or_request",
        nargs="?",
        help="Subcommand (propose/apply/verify/explain/history/undo/upgrade) "
             "OR the natural-language request when used in shorthand mode.",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Natural-language refactor request (when a subcommand is given).",
    )
    parser.add_argument("--apply", action="store_true",
        help="Apply proposals AND run the verification fix-loop.")
    parser.add_argument("--no-llm", action="store_true",
        help="Skip LLM calls (only useful for diagnostics).")
    parser.add_argument("--no-verify", action="store_true",
        help="Skip the post-apply fix-loop.")
    parser.add_argument("--include-siblings", action="store_true",
        help="Include sibling services from the same wrapper in retrieval.")
    parser.add_argument("--include-skeleton", action="store_true", default=None,
        help="Include source skeleton templates in retrieval (default in in-tree mode).")
    parser.add_argument("--max-files", type=int,
        default=int(os.environ.get("SKEL_REFACTOR_MAX_FILES", "8")),
        help="Cap the number of files the model can edit in one run.")
    parser.add_argument("--ollama-model", default=None,
        help="Override OLLAMA_MODEL for this run.")
    parser.add_argument("--ollama-url", default=None,
        help="Override OLLAMA_BASE_URL.")
    parser.add_argument("--ollama-temperature", type=float, default=None,
        help="Sampling temperature.")
    parser.add_argument("--fix-timeout-m", type=int,
        default=int(os.environ.get("SKEL_REFACTOR_FIX_TIMEOUT_M", "15")),
        help="Fix-loop budget in minutes.")
    parser.add_argument("--allow-dirty", action="store_true",
        help="Allow apply on a non-clean git tree.")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the built-in runtime self-test and exit.",
    )
    return parser.parse_args(argv)


def _prompt_for_request(*, progress: Any) -> str:
    progress.write("[ai] Enter request: ")
    progress.flush()
    try:
        request = input()
    except EOFError:
        progress.write("\n[ai] FAIL: no request received on stdin.\n")
        return ""
    except KeyboardInterrupt:
        progress.write("\n[ai] Cancelled.\n")
        return ""
    return request.strip()


def _open_progress(args: argparse.Namespace) -> Any:
    if args.quiet:
        class _Null:
            def write(self, _s: str) -> int: return 0
            def flush(self) -> None: pass
        return _Null()
    return sys.stderr


def main(service_dir: Path, argv: List[str]) -> int:
    """Entrypoint shared by ``./ai`` and ``_bin/skel-ai``."""

    if "--self-test" in argv:
        return _self_test()

    service_dir = Path(service_dir).resolve()
    if not service_dir.is_dir():
        print(f"Not a directory: {service_dir}", file=sys.stderr)
        return 1

    args = _parse_args(argv)
    progress = _open_progress(args)

    sub = args.subcommand_or_request
    if sub in _SUBCOMMANDS:
        request = args.request or ""
    else:
        request = sub or ""
        sub = "apply" if args.apply else "propose"

    if not request and sub == "propose" and not argv:
        request = _prompt_for_request(progress=progress)

    if sub == "history":
        return _cmd_history(service_dir)
    if sub == "explain":
        return _cmd_explain(service_dir)
    if sub == "undo":
        return _cmd_undo(service_dir, progress=progress)
    if sub == "verify":
        return _cmd_verify(service_dir, args, progress=progress)
    if sub == "upgrade":
        return _cmd_upgrade(service_dir, args, progress=progress)

    if not request:
        print(
            "ERROR: a natural-language REQUEST is required.\n"
            "Examples:\n"
            "  ./ai\n"
            "  ./ai \"add a /healthz endpoint\"\n"
            "  ./ai apply \"add a /healthz endpoint\"",
            file=sys.stderr,
        )
        return 1

    sidecar = _load_sidecar(service_dir)
    devskel = None
    try:
        devskel = detect_devskel(service_dir)
    except RefactorAbort as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    test_command = (sidecar or {}).get("test_command", "./test")

    include_skeleton = args.include_skeleton
    if include_skeleton is None:
        include_skeleton = devskel is not None

    ctx = RefactorContext(
        service_dir=service_dir,
        request=request,
        sidecar=sidecar,
        mode="in-tree" if devskel else "out-of-tree",
        devskel_root=devskel,
        include_siblings=bool(args.include_siblings),
        include_skeleton=bool(include_skeleton),
        max_files=int(args.max_files),
        test_command=test_command,
        fix_timeout_m=int(args.fix_timeout_m),
        allow_dirty=bool(args.allow_dirty),
        no_verify=bool(args.no_verify),
        no_llm=bool(args.no_llm),
    )

    progress.write(f"[ai] Mode: {ctx.mode}")
    if devskel:
        progress.write(f" (dev_skel found at {devskel})\n")
    else:
        progress.write(" (no dev_skel checkout reachable)\n")
    progress.write(
        f"[ai] RAG: {RagRunner.rag_label if ctx.mode == 'in-tree' else MinimalRunner.rag_label}\n"
    )

    if args.ollama_model:
        os.environ["OLLAMA_MODEL"] = args.ollama_model
    if args.ollama_url:
        os.environ["OLLAMA_BASE_URL"] = args.ollama_url
    if args.ollama_temperature is not None:
        os.environ["OLLAMA_TEMPERATURE"] = str(args.ollama_temperature)

    runner = build_runner(ctx, progress=progress)

    try:
        retrieved = runner.retrieve()
    except RefactorOllamaError as exc:
        progress.write(f"[ai] FAIL: {exc}\n")
        return 2
    except RefactorAbort as exc:
        progress.write(f"[ai] FAIL: {exc}\n")
        return 1

    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    (ctx.output_dir / "request.txt").write_text(request, encoding="utf-8")
    (ctx.output_dir / "context.json").write_text(
        _serialise_ctx(ctx), encoding="utf-8",
    )
    if retrieved:
        (ctx.output_dir / "retrieved").mkdir(exist_ok=True)
        (ctx.output_dir / "retrieved" / "chunks.md").write_text(
            retrieved, encoding="utf-8",
        )

    try:
        edits = runner.propose(retrieved)
    except RefactorOllamaError as exc:
        progress.write(f"[ai] FAIL: {exc}\n")
        return 2
    except RefactorParseError as exc:
        progress.write(f"[ai] FAIL: {exc}\n")
        return 1

    if not edits:
        progress.write("[ai] No edits proposed.\n")
        return 0

    proposals_dir = ctx.output_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    rationale_lines: List[str] = []
    for edit in edits:
        target = proposals_dir / edit.rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(edit.new_contents, encoding="utf-8")
        if edit.rationale:
            rationale_lines.append(f"## {edit.rel_path}\n\n{edit.rationale}\n")
    rationale_text = (
        "\n".join(rationale_lines) or "(no per-file rationale provided)\n"
    )
    (ctx.output_dir / "rationale.md").write_text(
        rationale_text, encoding="utf-8",
    )

    progress.write(
        f"[ai] {len(edits)} proposals written to "
        f"{ctx.output_dir.relative_to(service_dir)}\n"
    )
    for edit in edits:
        marker = "A" if not (service_dir / edit.rel_path).exists() else "M"
        progress.write(f"[ai] {marker}  {edit.rel_path}\n")

    head = service_dir / ".ai" / "HEAD"
    with contextlib.suppress(FileNotFoundError):
        head.unlink()
    try:
        head.symlink_to(ctx.output_dir.name)
    except (OSError, NotImplementedError):
        head.write_text(ctx.output_dir.name, encoding="utf-8")

    if sub == "propose":
        progress.write(
            "[ai] No edits applied (dry-run). "
            "Re-run with `./ai apply ...` to commit.\n"
        )
        return 0

    try:
        applied = runner.apply(edits)
    except RefactorAbort as exc:
        progress.write(f"[ai] FAIL: {exc}\n")
        return 1

    if applied.snapshot_ref:
        progress.write(
            f"[ai] Snapshot saved to {applied.snapshot_ref[:12]}... "
            "(./ai undo restores from here)\n"
        )
    elif applied.stash_ref:
        progress.write(
            f"[ai] Snapshot saved to {applied.stash_ref} "
            "(skel-ai pre-apply)\n"
        )

    (ctx.output_dir / "applied.json").write_text(json.dumps({
        "version": 1,
        "written": [str(p) for p in applied.written],
        "skipped": [(str(p), reason) for p, reason in applied.skipped],
        "stash_ref": applied.stash_ref,
        "snapshot_ref": applied.snapshot_ref,
        "applied_at_iso": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")

    if ctx.no_verify:
        progress.write("[ai] Skipping verification (--no-verify).\n")
        _drop_stash(ctx, applied)
        # Memory note: with --no-verify we don't know whether the
        # tests pass, so we record the run with `passed=None` so the
        # next propose can warn the model that the prior change was
        # not verified.
        _record_apply_to_memory(ctx, applied, None, rationale_text)
        return 0

    progress.write(f"[ai] Running {ctx.test_command} ...\n")
    test_result = runner.verify(applied)

    (ctx.output_dir / "verification.log").write_text(
        f"command: {test_result.command}\n"
        f"returncode: {test_result.returncode}\n"
        f"duration_s: {test_result.duration_s:.1f}\n\n"
        f"--- STDOUT ---\n{test_result.stdout}\n\n"
        f"--- STDERR ---\n{test_result.stderr}\n",
        encoding="utf-8",
    )

    if test_result.passed:
        progress.write(
            f"[ai] PASS in {test_result.duration_s:.1f}s — fix loop done.\n"
        )
        _drop_stash(ctx, applied)
        progress.write(
            f"[ai] Stash dropped. .ai/HEAD → {ctx.output_dir.name}\n"
        )
        _record_apply_to_memory(ctx, applied, test_result, rationale_text)
        return 0

    progress.write(
        f"[ai] FAIL after {test_result.duration_s/60:.1f}m "
        "— rolling back.\n"
    )
    _rollback(ctx, applied)
    # Memory note: even on rollback we record the failed attempt so
    # the next propose knows "X was tried and the test broke" and can
    # avoid the same dead end.
    _record_apply_to_memory(ctx, applied, test_result, rationale_text)
    return 3


def _serialise_ctx(ctx: RefactorContext) -> str:
    return json.dumps({
        "version": 1,
        "request": ctx.request,
        "mode": ctx.mode,
        "devskel_root": str(ctx.devskel_root) if ctx.devskel_root else None,
        "include_siblings": ctx.include_siblings,
        "include_skeleton": ctx.include_skeleton,
        "max_files": ctx.max_files,
        "test_command": ctx.test_command,
        "fix_timeout_m": ctx.fix_timeout_m,
        "ollama": {
            "model": os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b"),
            "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        },
        "sidecar": ctx.sidecar,
        "started_at_iso": datetime.now(timezone.utc).isoformat(),
    }, indent=2)


def _cmd_history(service_dir: Path) -> int:
    """List previous ./ai runs visible from this service.

    Output has two sections:
      1. **Project memory** — every applied run across every service in
         the wrapper, read from ``<wrapper>/.ai/memory.jsonl``. This is
         the cross-service log that gives the model continuity between
         calls. Only present after at least one apply has run.
      2. **Local runs** — the per-service ``<service>/.ai/<ts>-<sha>/``
         scratch dirs (proposals, applied edits, retrieved chunks,
         rationale). Includes both dry-runs and applied runs.

    The two layers complement each other: project memory is best for
    "what has the AI been doing across my whole codebase?", local runs
    are best for "what proposal did I review yesterday in this
    service?".
    """

    printed_anything = False

    # Section 1 — project-wide memory log.
    wrapper_memory, _service_memory = _memory_paths(service_dir)
    project_entries = _load_recent_memory(wrapper_memory, limit=20)
    if project_entries:
        print("== Project memory (cross-service, newest first) ==")
        for entry in reversed(project_entries):
            ts = entry.get("ts", "")
            svc = entry.get("service", "?")
            req = entry.get("request", "")[:70]
            passed = entry.get("passed")
            status = "PASS" if passed else "FAIL" if passed is False else "n/a"
            print(f"  [{ts}]  {svc:<20}  {status:4s}  {req}")
        printed_anything = True
        print()

    # Section 2 — local scratch runs in this service.
    root = service_dir / ".ai"
    runs: List[Path] = []
    if root.is_dir():
        runs = sorted(
            [p for p in root.iterdir()
             if p.is_dir() and p.name not in {".lock"}],
            reverse=True,
        )
    if runs:
        print(f"== Local runs in {service_dir.name} (newest first) ==")
        for r in runs:
            ctx_p = r / "context.json"
            applied_p = r / "applied.json"
            try:
                ctx = json.loads(ctx_p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            status = "applied" if applied_p.is_file() else "dry-run"
            print(f"  {r.name}  {status:8s}  {ctx.get('request', '')[:60]}")
        printed_anything = True

    if not printed_anything:
        print("(no refactor history)")
    return 0


def _cmd_explain(service_dir: Path) -> int:
    head = service_dir / ".ai" / "HEAD"
    target_dir: Optional[Path] = None
    if head.is_symlink():
        target_dir = (service_dir / ".ai" / os.readlink(head)).resolve()
    elif head.is_file():
        target_dir = service_dir / ".ai" / head.read_text(encoding="utf-8").strip()
    if target_dir is None or not (target_dir / "rationale.md").is_file():
        print("No previous run found.", file=sys.stderr)
        return 1
    sys.stdout.write((target_dir / "rationale.md").read_text(encoding="utf-8"))
    return 0


def _cmd_verify(
    service_dir: Path, args: argparse.Namespace, *, progress: Any,
) -> int:
    head = service_dir / ".ai" / "HEAD"
    if not (head.is_symlink() or head.is_file()):
        print("No previous run found.", file=sys.stderr)
        return 1
    target_name = (
        os.readlink(head) if head.is_symlink() else head.read_text().strip()
    )
    last = (service_dir / ".ai" / target_name).resolve()
    applied_path = last / "applied.json"
    if not applied_path.is_file():
        print(
            f"{last.name}: no applied.json (this run never went past --dry-run).",
            file=sys.stderr,
        )
        return 1

    payload = json.loads(applied_path.read_text(encoding="utf-8"))
    sidecar = _load_sidecar(service_dir)
    devskel = None
    with contextlib.suppress(RefactorAbort):
        devskel = detect_devskel(service_dir)
    test_command = (sidecar or {}).get("test_command", "./test")
    ctx = RefactorContext(
        service_dir=service_dir,
        request=json.loads((last / "context.json").read_text())["request"],
        sidecar=sidecar,
        mode="in-tree" if devskel else "out-of-tree",
        devskel_root=devskel,
        max_files=int(args.max_files),
        test_command=test_command,
        fix_timeout_m=int(args.fix_timeout_m),
    )
    applied = AppliedResult(
        written=[Path(p) for p in payload.get("written", [])],
        skipped=[(Path(p), reason) for p, reason in payload.get("skipped", [])],
        stash_ref=None,
    )
    runner = build_runner(ctx, progress=progress)
    test_result = runner.verify(applied)
    return 0 if test_result.passed else 3


def _cmd_undo(service_dir: Path, *, progress: Any) -> int:
    head = service_dir / ".ai" / "HEAD"
    if not (head.is_symlink() or head.is_file()):
        print("No previous run found.", file=sys.stderr)
        return 1
    target_name = (
        os.readlink(head) if head.is_symlink() else head.read_text().strip()
    )
    last = (service_dir / ".ai" / target_name).resolve()
    applied_path = last / "applied.json"
    if not applied_path.is_file():
        print("Last run was dry-run only; nothing to undo.", file=sys.stderr)
        return 1
    payload = json.loads(applied_path.read_text(encoding="utf-8"))
    snapshot = payload.get("snapshot_ref")
    if not snapshot:
        print("Snapshot ref missing — was this run pre-snapshot version?",
              file=sys.stderr)
        return 1

    branch = f"refactor-undo/{last.name}"
    try:
        _git("checkout", "-b", branch, cwd=service_dir)
        _git("stash", "apply", snapshot, cwd=service_dir)
    except subprocess.CalledProcessError as exc:
        print(f"git error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Restored to branch {branch}. Inspect, then either:\n"
        f"  git checkout - && git branch -D {branch}    # discard undo\n"
        f"  git checkout master && git merge {branch}   # keep undo\n"
    )
    return 0


# --------------------------------------------------------------------------- #
#  ./ai upgrade — pull skeleton-side changes into a generated service
# --------------------------------------------------------------------------- #


_CHANGELOG_HEADER_RE = re.compile(r"^## \[([^\]]+)\]")


def _semver_tuple(version: str) -> Tuple[int, int, int]:
    """Parse a semver string into a ``(major, minor, patch)`` tuple.

    Raises :class:`ValueError` when ``version`` is not parseable so
    callers can fall back to a more conservative selection strategy.
    Pre-release / build metadata after ``-`` or ``+`` is stripped
    from the patch component before integer conversion.
    """

    parts = version.strip().split(".")
    if len(parts) < 3:
        raise ValueError(version)
    major, minor, rest = parts[0], parts[1], parts[2]
    for sep in ("-", "+"):
        if sep in rest:
            rest = rest.split(sep, 1)[0]
            break
    return (int(major), int(minor), int(rest))


def _changelog_excerpt(changelog: Path, old: str, new: str) -> str:
    """Return CHANGELOG entries strictly above ``old``, up to ``new``.

    The skeleton's CHANGELOG.md follows "Keep a Changelog": each
    version block opens with ``## [VERSION] - DATE``. We select every
    block whose version is ``> old`` and ``<= new`` (semver order).
    Returns the joined Markdown body — empty when no entries match
    or the file is missing. Unparseable versions are kept conservatively
    so a typo in CHANGELOG never silently drops context from the
    upgrade prompt.
    """

    if not changelog.is_file():
        return ""
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError:
        return ""

    entries: List[Tuple[str, str]] = []
    cur_version: Optional[str] = None
    cur_body: List[str] = []
    for line in text.splitlines():
        m = _CHANGELOG_HEADER_RE.match(line)
        if m:
            if cur_version is not None:
                entries.append(
                    (cur_version, "\n".join(cur_body).strip())
                )
            cur_version = m.group(1).strip()
            cur_body = [line]
        elif cur_version is not None:
            cur_body.append(line)
    if cur_version is not None:
        entries.append((cur_version, "\n".join(cur_body).strip()))

    try:
        old_tup = _semver_tuple(old)
        new_tup = _semver_tuple(new)
    except ValueError:
        old_tup = new_tup = None  # type: ignore[assignment]

    selected: List[str] = []
    for version, body in entries:
        if old_tup is None:
            selected.append(body)
            continue
        try:
            v_tup = _semver_tuple(version)
        except ValueError:
            selected.append(body)
            continue
        if v_tup > old_tup and v_tup <= new_tup:
            selected.append(body)
    return "\n\n".join(selected)


def _cmd_upgrade(
    service_dir: Path, args: argparse.Namespace, *, progress: Any,
) -> int:
    """Pull skeleton-side changes since this service was generated.

    Reads ``skeleton_version`` from the sidecar, compares against the
    skeleton's current ``VERSION`` file, extracts the matching
    CHANGELOG.md entries, and dispatches them as a synthesised refactor
    request through the standard propose/apply flow. On a successful
    apply the sidecar's ``skeleton_version`` is rewritten so subsequent
    upgrades start from the new baseline.

    Dry-run by default (``./ai upgrade``). Pass ``--apply`` to commit
    (``./ai upgrade --apply`` or ``./ai apply upgrade`` both work).
    """

    sidecar = _load_sidecar(service_dir)
    if not sidecar:
        progress.write(
            "[ai] FAIL: missing .skel_context.json — cannot determine "
            "source skeleton (regenerate with skel-gen >= 2026-04).\n"
        )
        return 1

    skeleton_name = sidecar.get("skeleton_name")
    service_version = (sidecar.get("skeleton_version") or "").strip()
    if not skeleton_name:
        progress.write("[ai] FAIL: sidecar missing skeleton_name.\n")
        return 1
    if not service_version:
        progress.write(
            "[ai] FAIL: sidecar missing skeleton_version "
            "(regenerate with the latest skel-gen).\n"
        )
        return 1

    try:
        devskel = detect_devskel(service_dir)
    except RefactorAbort as exc:
        progress.write(f"[ai] FAIL: {exc}\n")
        return 1
    if devskel is None:
        progress.write(
            "[ai] FAIL: dev_skel checkout not reachable. "
            "Set $DEV_SKEL_ROOT to enable upgrades.\n"
        )
        return 1

    skel_dir = devskel / "_skels" / skeleton_name
    version_file = skel_dir / "VERSION"
    changelog_file = skel_dir / "CHANGELOG.md"
    if not version_file.is_file():
        progress.write(
            f"[ai] FAIL: skeleton has no VERSION file ({version_file}).\n"
        )
        return 1
    skel_version = version_file.read_text(encoding="utf-8").strip()
    if not skel_version:
        progress.write(f"[ai] FAIL: empty VERSION at {version_file}.\n")
        return 1

    if skel_version == service_version:
        progress.write(
            f"[ai] {skeleton_name} is already at v{skel_version} "
            "— nothing to upgrade.\n"
        )
        return 0

    excerpt = _changelog_excerpt(
        changelog_file, service_version, skel_version,
    )
    if not excerpt.strip():
        excerpt = (
            f"(No CHANGELOG.md entries found between v{service_version} "
            f"and v{skel_version}; consult the skeleton diff manually.)"
        )

    progress.write(
        f"[ai] {skeleton_name}: v{service_version} → v{skel_version}\n"
    )
    progress.write("[ai] CHANGELOG excerpt:\n")
    for line in excerpt.splitlines():
        progress.write(f"[ai]   {line}\n")

    request = (
        f"Upgrade this service from skeleton version {service_version} "
        f"to {skel_version}. The skeleton (`{skeleton_name}`) shipped "
        f"these changes since this service was generated:\n\n"
        f"{excerpt}\n\n"
        "Apply equivalent changes to this service. Preserve any local "
        "customisation that does not directly conflict with the upgrade. "
        "Do NOT touch files outside the patterns the skeleton defines."
    )

    sub = "apply" if args.apply else "propose"
    new_argv: List[str] = [sub, request, "--include-skeleton"]
    if args.allow_dirty:
        new_argv.append("--allow-dirty")
    if args.no_verify:
        new_argv.append("--no-verify")
    if args.no_llm:
        new_argv.append("--no-llm")
    if args.verbose:
        new_argv.append("--verbose")
    if args.quiet:
        new_argv.append("--quiet")

    rc = main(service_dir, new_argv)
    if rc == 0 and sub == "apply":
        sidecar["skeleton_version"] = skel_version
        sidecar["upgraded_at"] = datetime.now(timezone.utc).isoformat()
        try:
            (service_dir / ".skel_context.json").write_text(
                json.dumps(sidecar, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            progress.write(
                f"[ai] Sidecar skeleton_version → {skel_version}\n"
            )
        except OSError as exc:
            progress.write(
                "[ai] WARN: could not update sidecar "
                f"skeleton_version: {exc}\n"
            )
    return rc


# --------------------------------------------------------------------------- #
#  Self-test
# --------------------------------------------------------------------------- #


def _self_test() -> int:
    """Smoke checks runnable as ``python3 dev_skel_refactor_runtime.py --self-test``."""

    raw = (
        "RATIONALE:\n"
        "app/foo.py: example refactor\n"
        "\n"
        "FILES: 1\n"
        "\n"
        "FILE: app/foo.py\n"
        "LANG: python\n"
        "print('hi')\n"
        "ENDFILE\n"
    )
    edits = _split_refactor_response(raw, max_files=8)
    assert len(edits) == 1, edits
    assert edits[0].rel_path == "app/foo.py"
    assert edits[0].language == "python"
    assert "print('hi')" in edits[0].new_contents
    assert "example refactor" in edits[0].rationale, edits[0].rationale

    bad = "FILE: ../../etc/passwd\nx\nENDFILE\n"
    try:
        _split_refactor_response(bad, max_files=8)
    except RefactorParseError:
        pass
    else:
        raise AssertionError("path traversal not rejected")

    empty = "FILE: app/x.py\nENDFILE\n"
    try:
        _split_refactor_response(empty, max_files=8)
    except RefactorParseError:
        pass
    else:
        raise AssertionError("empty body not rejected")

    assert "extract" not in _tokenise("extract a service layer")
    assert "service" not in _tokenise("extract a service layer")

    print("[self-test] OK — runtime is importable and parser is sane.")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test())
    if len(sys.argv) < 2:
        print("Usage: dev_skel_refactor_runtime.py SERVICE_DIR [args]",
              file=sys.stderr)
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1]), sys.argv[2:]))
