#!/usr/bin/env python3
"""Shared helpers for dev_skel CLI tools.

This module centralizes configuration loading and common operations
so individual entrypoints (install/update/sync/skel-list/skel-gen)
can stay thin while keeping behavior consistent with the previous
shell implementations.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from string import Template
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


CONFIG_KEYS: List[str] = [
    "SKEL_DIR",
    "DEV_DIR",
    "EXCLUDES_FILE",
    "DEV_SYNC_DIR",
    "SYNC_SSH_HOST",
    "SYNC_DEST_DIR",
    "UPDATE_EXCLUDES_FILE",
]


@dataclass
class DevSkelConfig:
    skel_dir: Path
    dev_dir: Path
    excludes_file: Path
    dev_sync_dir: Path
    sync_ssh_host: str
    sync_dest_dir: str
    update_excludes_file: Path
    user_conf: Path


def _default_env() -> Dict[str, str]:
    home = Path.home()
    skel_dir = os.environ.get("SKEL_DIR", str(home / "dev_skel"))
    skel_dir_path = Path(skel_dir)
    return {
        "SKEL_DIR": skel_dir,
        "DEV_DIR": os.environ.get("DEV_DIR", str(home / "dev")),
        "EXCLUDES_FILE": os.environ.get(
            "EXCLUDES_FILE", str(skel_dir_path / "_bin/rsync-common-excludes.txt")
        ),
        "DEV_SYNC_DIR": os.environ.get("DEV_SYNC_DIR", str(home / "dev_sync")),
        "SYNC_SSH_HOST": os.environ.get("SYNC_SSH_HOST", ""),
        "SYNC_DEST_DIR": os.environ.get("SYNC_DEST_DIR", ""),
        "UPDATE_EXCLUDES_FILE": os.environ.get(
            "UPDATE_EXCLUDES_FILE", str(skel_dir_path / "_bin/rsync-update-excludes.txt")
        ),
    }


def _parse_user_conf(conf_path: Path, base_env: Dict[str, str]) -> Dict[str, str]:
    """Parse a shell-style config file by delegating to a subshell.

    This preserves shell variable expansion semantics while limiting
    the surface area to the known CONFIG_KEYS. If the config file is
    missing or cannot be sourced, the base_env is returned unchanged.
    """

    if not conf_path.is_file():
        return base_env

    script = """
set -a
source "$1"
for key in {keys}; do
  printf "%s=%s\n" "$key" "${!key}"
done
""".format(keys=" ".join(CONFIG_KEYS))

    try:
        proc = subprocess.run(
            ["bash", "-c", script, "--", str(conf_path)],
            check=True,
            capture_output=True,
            text=True,
            env=base_env,
        )
    except subprocess.CalledProcessError:
        return base_env

    result = dict(base_env)
    for line in proc.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in CONFIG_KEYS and value:
            result[key] = value
    return result


def load_config() -> DevSkelConfig:
    base_env = _default_env()
    user_conf = Path.home() / ".dev_skel.conf"
    merged = _parse_user_conf(user_conf, base_env)
    skel_dir = Path(merged["SKEL_DIR"]).expanduser().resolve()

    # Recompute defaults that depend on SKEL_DIR if user did not override
    excludes_file = merged["EXCLUDES_FILE"] or str(skel_dir / "_bin/rsync-common-excludes.txt")
    update_excludes = merged["UPDATE_EXCLUDES_FILE"] or str(
        skel_dir / "_bin/rsync-update-excludes.txt"
    )

    return DevSkelConfig(
        skel_dir=skel_dir,
        dev_dir=Path(merged["DEV_DIR"]).expanduser().resolve(),
        excludes_file=Path(excludes_file).expanduser().resolve(),
        dev_sync_dir=Path(merged["DEV_SYNC_DIR"]).expanduser().resolve(),
        sync_ssh_host=merged["SYNC_SSH_HOST"],
        sync_dest_dir=merged["SYNC_DEST_DIR"],
        update_excludes_file=Path(update_excludes).expanduser().resolve(),
        user_conf=user_conf,
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def require_dir(path: Path, message: str) -> None:
    if not path.is_dir():
        raise SystemExit(message)


def detect_root(script_dir: Path, configured_skel_dir: Path) -> Path:
    candidates = [configured_skel_dir, script_dir.parent, Path.home() / "dev_skel"]
    for candidate in candidates:
        if (candidate / "_skels").is_dir():
            return candidate
    raise SystemExit(
        "Error: Could not locate _skels directory. Set SKEL_DIR or keep _bin and _skels together."
    )


def run_rsync(args: List[str]) -> None:
    subprocess.run(args, check=True)


def update_dev_dir(cfg: DevSkelConfig, require_existing: bool = True) -> None:
    if require_existing and not cfg.dev_dir.is_dir():
        raise SystemExit(
            f"Error: {cfg.dev_dir} does not exist.\nRun install-dev-skel first to set up the dev directory."
        )

    rsync_cmd = [
        "rsync",
        "-av",
        "--progress",
        "--exclude-from",
        str(cfg.excludes_file),
        "--exclude-from",
        str(cfg.update_excludes_file),
        f"{cfg.skel_dir}/",
        f"{cfg.dev_dir}/",
    ]
    run_rsync(rsync_cmd)


def install_dev_dir(cfg: DevSkelConfig) -> None:
    ensure_dir(cfg.dev_dir)
    update_dev_dir(cfg, require_existing=False)


def sync_to_remote(host: str, src_dir: Path, dest_dir: str, excludes_file: Path) -> None:
    rsync_cmd = [
        "rsync",
        "-az",
        "--delete",
        "--progress",
        "--exclude-from",
        str(excludes_file),
        "-e",
        "ssh",
        f"{src_dir}/",
        f"{host}:{dest_dir}/",
    ]
    run_rsync(rsync_cmd)


def list_skeletons(skels_dir: Path) -> List[str]:
    if not skels_dir.is_dir():
        raise SystemExit(f"No _skels directory found at: {skels_dir}")

    names: List[str] = []
    for entry in skels_dir.iterdir():
        if entry.is_dir() and (entry / "Makefile").is_file():
            names.append(entry.name)
    return sorted(names)


def choose_service_subdir(main_dir: Path, base_name: str) -> str:
    n = 1
    candidate = base_name
    while (main_dir / candidate).exists():
        candidate = f"{base_name}-{n}"
        n += 1
    return candidate


def ensure_make_available() -> None:
    if not shutil.which("make"):
        raise SystemExit("Error: make is required to run skeleton generators.")


def run_gen_command(skel_path: Path, target: Path, service_subdir: str) -> None:
    gen_script = skel_path / "gen"
    if gen_script.is_file():
        subprocess.run(["bash", str(gen_script), str(target), service_subdir], check=True)
    else:
        raise SystemExit(f"Error: generator not found: {gen_script}")


def render_template_file(path: Path, context: Dict[str, str]) -> bool:
    if not path.is_file():
        return False

    try:
        raw = path.read_text(encoding="utf-8")
        rendered = Template(raw).safe_substitute(context)
    except ValueError as exc:
        print(f"Warning: skipping template rendering for {path}: {exc}")
        return False

    if rendered != raw:
        path.write_text(rendered, encoding="utf-8")
    return True


def render_agents_template(target: Path, service_subdir: str, skeleton_name: str, project_name: str) -> None:
    """Render AGENTS.md and CLAUDE.md templates inside a freshly generated project.

    The same context is used for both files so cross-agent and Claude-specific
    rules stay in sync. Both the wrapper directory and the inner service
    directory are checked.
    """

    context = {
        "project_name": project_name,
        "service_dir": service_subdir,
        "skeleton_name": skeleton_name,
        "skeleton_doc": f"_docs/{skeleton_name}.md",
    }

    service_dir = target / service_subdir
    candidates = [
        service_dir / "AGENTS.md",
        target / "AGENTS.md",
        service_dir / "CLAUDE.md",
        target / "CLAUDE.md",
    ]
    for candidate in candidates:
        render_template_file(candidate, context)


def default_service_base(skel_name: str) -> str:
    mapping = {
        "python-fastapi-skel": "backend",
        "python-django-skel": "backend",
        "python-flask-skel": "backend",
        "ts-react-skel": "frontend",
    }
    return mapping.get(skel_name, "service")


def generate_project(root: Path, skel_name: str, proj_name: str, service_override: str | None) -> str:
    skels_dir = root / "_skels"
    require_dir(skels_dir, f"No _skels directory found at: {skels_dir}")

    skel_path = skels_dir / skel_name
    require_dir(skel_path, f"Error: skeleton not found: {skel_name} (expected at {skel_path})")

    if "/" in proj_name:
        raise SystemExit("Error: proj_name must be a leaf directory name (no / characters)")

    target = Path.cwd() / proj_name
    main_dir = target

    ensure_dir(target.parent)

    base = service_override or default_service_base(skel_name)
    service_subdir = base
    if (main_dir / service_subdir).exists():
        service_subdir = choose_service_subdir(main_dir, base)

    run_gen_command(skel_path, target, service_subdir)
    return service_subdir
