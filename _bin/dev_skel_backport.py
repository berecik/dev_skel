"""Maintainer-side skeleton backport command.

Implements the first internal slice of ``SKEL_BACKPORT_COMMAND.md``:

* ``generate`` creates a fresh test wrapper under ``_test_projects/``.
* ``propose`` inspects a generated service and records backportable files.
* ``apply`` writes those files back into the resolved skeleton tree.

The current implementation intentionally keeps the mapping conservative:
only files whose relative paths already exist inside the target skeleton
are considered backportable. This is enough to realise the initial
service-to-template scenario while keeping writes inside maintainer-owned
template trees.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from dev_skel_lib import generate_project, slugify_service_name


class BackportAbort(RuntimeError):
    """Raised when the command cannot safely continue."""


@dataclass
class BackportCandidate:
    rel_path: str
    skeleton_path: Path
    service_path: Path
    reason: str


def _repo_root(start: Path) -> Path:
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "_bin").is_dir() and (candidate / "_skels").is_dir():
            return candidate
    raise BackportAbort(f"could not locate dev_skel root from {start}")


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="_bin/skel-backport",
        description=(
            "Backport edits from a generated service into its source skeleton."
        ),
    )
    parser.add_argument(
        "command",
        choices=("generate", "propose", "apply"),
        help="Operation to run.",
    )
    parser.add_argument(
        "target",
        help="Skeleton name for `generate`, generated service path otherwise.",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Leaf wrapper name for `generate` (created under _test_projects/).",
    )
    parser.add_argument(
        "--service-name",
        default=None,
        help="Optional display name passed through to skeleton generation.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Override the run artifact directory.",
    )
    parser.add_argument(
        "--skeleton",
        default=None,
        help="Override the resolved skeleton path/name for propose/apply.",
    )
    return parser.parse_args(argv)


def _slug_from_target(target: str) -> str:
    name = target[:-5] if target.endswith("-skel") else target
    return slugify_service_name(name.replace("_", " ").replace("-", " "))


@contextlib.contextmanager
def _pushd(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _artifact_path(root: Path, target: str, override: Optional[str]) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    digest = hashlib.sha1(target.encode("utf-8")).hexdigest()[:8]
    return root / ".ai" / "backport" / f"{stamp}-{digest}"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BackportAbort(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BackportAbort(f"invalid JSON in {path}: {exc}") from exc


def _resolve_service_path(root: Path, target: str) -> Path:
    service = Path(target)
    if not service.is_absolute():
        service = (root / target).resolve()
    if not service.is_dir():
        raise BackportAbort(f"generated service not found: {service}")
    return service


def _resolve_skeleton_path(root: Path, service_dir: Path, override: Optional[str]) -> Path:
    if override:
        candidate = Path(override)
        if not candidate.is_absolute():
            candidate = root / "_skels" / override
        candidate = candidate.resolve()
        if candidate.is_dir():
            return candidate
        raise BackportAbort(f"skeleton override not found: {candidate}")

    sidecar = service_dir / ".skel_context.json"
    if not sidecar.is_file():
        raise BackportAbort(f"missing sidecar: {sidecar}")
    payload = _load_json(sidecar)
    rel = payload.get("skeleton_path_rel")
    if not isinstance(rel, str) or not rel.strip():
        raise BackportAbort(f"sidecar missing skeleton_path_rel: {sidecar}")
    candidate = (service_dir.parent / rel).resolve()
    if candidate.is_dir():
        return candidate

    fallback = (root / rel).resolve()
    if fallback.is_dir():
        return fallback
    raise BackportAbort(
        f"could not resolve skeleton path {rel!r} from {service_dir}"
    )


def _safe_relative(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise BackportAbort(f"path escapes allowed root: {path}") from exc
    return rel.as_posix()


def _iter_service_files(service_dir: Path) -> Iterator[Path]:
    for path in sorted(service_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(service_dir)
        if rel.parts[0].startswith("."):
            continue
        if rel.parts[0] in {".git", ".ai", "node_modules", "__pycache__"}:
            continue
        yield path


def _collect_candidates(service_dir: Path, skeleton_dir: Path) -> List[BackportCandidate]:
    candidates: List[BackportCandidate] = []
    for service_path in _iter_service_files(service_dir):
        rel = service_path.relative_to(service_dir)
        skeleton_path = skeleton_dir / rel
        if not skeleton_path.is_file():
            continue
        try:
            service_text = service_path.read_text(encoding="utf-8")
            skeleton_text = skeleton_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if service_text == skeleton_text:
            continue
        candidates.append(
            BackportCandidate(
                rel_path=rel.as_posix(),
                skeleton_path=skeleton_path,
                service_path=service_path,
                reason="service file differs from same-relative skeleton file",
            )
        )
    return candidates


def _write_artifacts(
    artifact_dir: Path,
    *,
    command: str,
    service_dir: Optional[Path],
    skeleton_dir: Optional[Path],
    candidates: List[BackportCandidate],
    generated_service: Optional[Path] = None,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "command": command,
        "service_dir": str(service_dir) if service_dir else None,
        "skeleton_dir": str(skeleton_dir) if skeleton_dir else None,
        "generated_service": str(generated_service) if generated_service else None,
        "candidates": [
            {
                "rel_path": c.rel_path,
                "service_path": str(c.service_path),
                "skeleton_path": str(c.skeleton_path),
                "reason": c.reason,
            }
            for c in candidates
        ],
    }
    (artifact_dir / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cmd_generate(root: Path, args: argparse.Namespace, *, progress: Any) -> int:
    skel_name = args.target
    project_name = args.project_name or f"backport-{_slug_from_target(skel_name)}"
    tests_root = root / "_test_projects"
    tests_root.mkdir(parents=True, exist_ok=True)
    with _pushd(tests_root):
        service_subdir = generate_project(
            root,
            skel_name,
            project_name,
            service_name=args.service_name,
        )
    generated_service = (tests_root / project_name / service_subdir).resolve()
    artifact_dir = _artifact_path(root, str(generated_service), args.artifact_dir)
    _write_artifacts(
        artifact_dir,
        command="generate",
        service_dir=None,
        skeleton_dir=None,
        candidates=[],
        generated_service=generated_service,
    )
    progress.write(f"[backport] generated {generated_service}\n")
    progress.write(f"[backport] artifacts: {artifact_dir}\n")
    return 0


_SEMVER_RE = __import__("re").compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def _bump_patch(version: str) -> str:
    """Return ``version`` with the patch component incremented.

    Falls back to ``"0.1.0"`` when the input is unparseable so a
    typo in the existing VERSION file doesn't block a backport.
    """

    match = _SEMVER_RE.match(version.strip())
    if not match:
        return "0.1.0"
    major, minor, patch = (int(g) for g in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def _bump_skeleton_version(
    skeleton_dir: Path,
    candidates: List[BackportCandidate],
    *,
    progress: Any,
) -> Optional[Tuple[str, str]]:
    """Increment ``<skel>/VERSION`` and append a CHANGELOG.md entry.

    Returns ``(old, new)`` so callers can surface the bump in their
    artefacts. Returns ``None`` when there is nothing to bump (no
    candidates) so a clean apply leaves the version untouched.

    The CHANGELOG entry lists each backported file. Format follows
    "Keep a Changelog" (``## [VERSION] - YYYY-MM-DD``) so existing
    parsers (and ``./ai upgrade``) can extract the diff per version.
    """

    if not candidates:
        return None

    version_file = skeleton_dir / "VERSION"
    changelog = skeleton_dir / "CHANGELOG.md"

    old = "0.1.0"
    if version_file.is_file():
        try:
            old = version_file.read_text(encoding="utf-8").strip() or old
        except OSError:
            pass
    new = _bump_patch(old)

    try:
        version_file.write_text(new + "\n", encoding="utf-8")
    except OSError as exc:
        progress.write(
            f"[backport] WARN: could not write {version_file}: {exc}\n"
        )
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_word = "file" if len(candidates) == 1 else "files"
    entry_lines: List[str] = [
        f"## [{new}] - {today}",
        "",
        f"Backported from a generated service via `_bin/skel-backport apply` "
        f"({len(candidates)} {file_word}):",
        "",
    ]
    for candidate in candidates:
        entry_lines.append(f"- `{candidate.rel_path}` — {candidate.reason}")
    entry_lines.append("")

    body = "\n".join(entry_lines)

    if changelog.is_file():
        try:
            existing = changelog.read_text(encoding="utf-8")
        except OSError:
            existing = "# Changelog\n\n"
        # Insert the new entry below the H1 (and any preamble) but
        # ABOVE the most recent existing version section. The
        # simplest reliable splice: find the first "## [" header and
        # insert before it. If none exists we append.
        marker_idx = existing.find("\n## [")
        if marker_idx >= 0:
            head = existing[:marker_idx + 1]
            tail = existing[marker_idx + 1:]
            updated = head + body + "\n" + tail
        else:
            updated = existing.rstrip() + "\n\n" + body
    else:
        updated = (
            f"# Changelog\n\n"
            f"All notable changes to this skeleton are recorded here.\n"
            f"Format: [Keep a Changelog]; versions: [Semantic Versioning].\n\n"
            + body
        )

    try:
        changelog.write_text(updated, encoding="utf-8")
    except OSError as exc:
        progress.write(
            f"[backport] WARN: could not write {changelog}: {exc}\n"
        )
        return None

    progress.write(
        f"[backport] bumped {skeleton_dir.name} version: {old} → {new}\n"
    )
    return (old, new)


def _cmd_propose_or_apply(
    root: Path,
    args: argparse.Namespace,
    *,
    progress: Any,
    apply_changes: bool,
) -> int:
    service_dir = _resolve_service_path(root, args.target)
    skeleton_dir = _resolve_skeleton_path(root, service_dir, args.skeleton)
    _safe_relative(skeleton_dir, root / "_skels")
    candidates = _collect_candidates(service_dir, skeleton_dir)
    artifact_dir = _artifact_path(root, str(service_dir), args.artifact_dir)
    _write_artifacts(
        artifact_dir,
        command="apply" if apply_changes else "propose",
        service_dir=service_dir,
        skeleton_dir=skeleton_dir,
        candidates=candidates,
    )
    if not candidates:
        progress.write("[backport] no backportable changes found\n")
        progress.write(f"[backport] artifacts: {artifact_dir}\n")
        return 0

    for candidate in candidates:
        progress.write(
            f"[backport] {'apply' if apply_changes else 'propose'} {candidate.rel_path}\n"
        )
        if apply_changes:
            candidate.skeleton_path.write_text(
                candidate.service_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    if apply_changes:
        # Bump VERSION + append CHANGELOG.md so subsequent
        # `./ai upgrade` runs can replay these changes against
        # already-generated services. Best-effort — write failures
        # surface as a warning rather than aborting the apply.
        _bump_skeleton_version(skeleton_dir, candidates, progress=progress)

    progress.write(f"[backport] artifacts: {artifact_dir}\n")
    return 0


def main(argv: List[str], *, cwd: Optional[Path] = None, progress: Any = None) -> int:
    root = _repo_root(cwd or Path.cwd())
    args = _parse_args(argv)
    progress = progress or sys.stderr
    try:
        if args.command == "generate":
            return _cmd_generate(root, args, progress=progress)
        if args.command == "propose":
            return _cmd_propose_or_apply(root, args, progress=progress, apply_changes=False)
        return _cmd_propose_or_apply(root, args, progress=progress, apply_changes=True)
    except BackportAbort as exc:
        progress.write(f"[backport] FAIL: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
