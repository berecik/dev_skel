#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


__all__ = [
    "RefactorContext",
    "FileEdit",
    "AppliedResult",
    "detect_devskel",
    "build_runner",
    "main",
]


@dataclass
class FileEdit:
    rel_path: str
    language: str
    new_contents: str
    rationale: str = ""
    is_new_file: bool = False


@dataclass
class AppliedResult:
    written: List[Path]
    skipped: List[Tuple[Path, str]]
    stash_ref: Optional[str] = None


@dataclass
class RefactorContext:
    service_dir: Path
    request: str
    sidecar: Optional[Dict[str, Any]]
    mode: str
    devskel_root: Optional[Path]
    include_siblings: bool = False
    include_skeleton: bool = True
    max_files: int = 8
    test_command: str = "./test"
    fix_timeout_m: int = 15
    output_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
        sha = hashlib.sha256(self.request.encode("utf-8")).hexdigest()[:6]
        self.output_dir = self.service_dir / ".refactor" / f"{ts}-{sha}"


def _read_sidecar(service_dir: Path) -> Optional[Dict[str, Any]]:
    sidecar = service_dir / ".skel_context.json"
    if not sidecar.is_file():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _looks_like_devskel_root(path: Path) -> bool:
    return (path / "_skels").is_dir() and (path / "_bin" / "skel-gen-ai").is_file()


def detect_devskel(service_dir: Path) -> Optional[Path]:
    env_root = os.environ.get("DEV_SKEL_ROOT")
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if _looks_like_devskel_root(root):
            return root
    for cur in [service_dir, *service_dir.parents, Path.cwd(), *Path.cwd().parents]:
        if _looks_like_devskel_root(cur):
            return cur
    for candidate in (
        Path.home() / "dev_skel",
        Path.home() / "src" / "dev_skel",
        Path("/opt/dev_skel"),
        Path("/usr/local/share/dev_skel"),
    ):
        if _looks_like_devskel_root(candidate):
            return candidate
    return None


class MinimalRunner:
    def __init__(self, ctx: RefactorContext) -> None:
        self.ctx = ctx

    def retrieve(self) -> str:
        snippets: List[str] = []
        tokens = [tok.lower() for tok in self.ctx.request.replace("/", " ").split() if len(tok) > 2]
        for path in sorted(self.ctx.service_dir.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                rel = path.relative_to(self.ctx.service_dir)
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            score = sum(tok in str(rel).lower() or tok in text.lower() for tok in tokens)
            if score <= 0:
                continue
            snippets.append(f"### {rel}\n```\n{text[:4000].rstrip()}\n```")
            if len(snippets) >= self.ctx.max_files:
                break
        return "\n\n".join(snippets) if snippets else "_(no relevant context retrieved)_"

    def propose(self, retrieved: str) -> List[FileEdit]:
        raise RuntimeError("Out-of-tree refactor proposals are not implemented yet")


def build_runner(ctx: RefactorContext) -> Any:
    return MinimalRunner(ctx)


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="refactor")
    parser.add_argument("request", nargs="?", default="")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(service_dir: Path | None = None, argv: Optional[List[str]] = None) -> int:
    args = _parse_args(list(argv or sys.argv[1:]))
    if args.self_test:
        return 0
    resolved = (service_dir or Path.cwd()).resolve()
    sidecar = _read_sidecar(resolved)
    devskel_root = detect_devskel(resolved)
    ctx = RefactorContext(
        service_dir=resolved,
        request=args.request,
        sidecar=sidecar,
        mode="in-tree" if devskel_root else "out-of-tree",
        devskel_root=devskel_root,
    )
    runner = build_runner(ctx)
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    (ctx.output_dir / "request.txt").write_text(ctx.request, encoding="utf-8")
    (ctx.output_dir / "context.json").write_text(
        json.dumps(
            {
                "mode": ctx.mode,
                "service_dir": str(ctx.service_dir),
                "devskel_root": str(ctx.devskel_root) if ctx.devskel_root else None,
                "sidecar": ctx.sidecar,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    retrieved = runner.retrieve()
    retrieved_dir = ctx.output_dir / "retrieved"
    retrieved_dir.mkdir(parents=True, exist_ok=True)
    (retrieved_dir / "chunks.md").write_text(retrieved, encoding="utf-8")
    print(f"[refactor] Mode: {ctx.mode}")
    print(f"[refactor] Proposal directory: {ctx.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
