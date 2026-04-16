from __future__ import annotations

import sys
from pathlib import Path


_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


from dev_skel_refactor_runtime import RefactorContext, detect_devskel, main


def test_self_test_exits_zero() -> None:
    assert main(argv=["--self-test"]) == 0


def test_refactor_context_builds_output_dir(tmp_path: Path) -> None:
    ctx = RefactorContext(
        service_dir=tmp_path,
        request="add healthz",
        sidecar=None,
        mode="out-of-tree",
        devskel_root=None,
    )
    assert ctx.output_dir.parent == tmp_path / ".refactor"
    assert ctx.output_dir.name.endswith(hash("add healthz").__str__()) is False


def test_detect_devskel_uses_env_root(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "dev_skel"
    (repo / "_skels").mkdir(parents=True)
    (repo / "_bin").mkdir(parents=True)
    (repo / "_bin" / "skel-gen-ai").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("DEV_SKEL_ROOT", str(repo))
    assert detect_devskel(tmp_path) == repo
