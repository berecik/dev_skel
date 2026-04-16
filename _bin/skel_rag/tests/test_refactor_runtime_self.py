from __future__ import annotations

import sys
from pathlib import Path


_BIN = Path(__file__).resolve().parents[2]
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))


import dev_skel_refactor_runtime as runtime
from dev_skel_refactor_runtime import RefactorContext, detect_devskel, main


def test_self_test_exits_zero() -> None:
    assert main(Path.cwd(), ["--self-test"]) == 0


def test_refactor_context_builds_output_dir(tmp_path: Path) -> None:
    ctx = RefactorContext(
        service_dir=tmp_path,
        request="add healthz",
        sidecar=None,
        mode="out-of-tree",
        devskel_root=None,
    )
    assert ctx.output_dir.parent == tmp_path / ".ai"
    assert ctx.output_dir.name.endswith(hash("add healthz").__str__()) is False


def test_detect_devskel_uses_env_root(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "dev_skel"
    (repo / "_skels").mkdir(parents=True)
    (repo / "_skels" / "_common").mkdir(parents=True)
    (repo / "_bin").mkdir(parents=True)
    (repo / "_bin" / "skel-gen-ai").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("DEV_SKEL_ROOT", str(repo))
    assert detect_devskel(tmp_path) == repo


def test_main_accepts_prompt_shorthand_without_subcommand(
    tmp_path: Path, monkeypatch,
) -> None:
    seen: dict[str, object] = {}

    class _Runner:
        def retrieve(self) -> str:
            return ""

        def propose(self, _retrieved: str):
            seen["request"] = seen["ctx"].request
            return []

    monkeypatch.setattr(runtime, "_load_sidecar", lambda _service_dir: None)
    monkeypatch.setattr(runtime, "detect_devskel", lambda _service_dir: None)

    def _build_runner(ctx, *, progress=None):
        seen["ctx"] = ctx
        seen["progress"] = progress
        return _Runner()

    monkeypatch.setattr(runtime, "build_runner", _build_runner)

    assert main(tmp_path, ["add healthz endpoint"]) == 0
    assert seen["request"] == "add healthz endpoint"


def test_main_prompts_interactively_when_no_args(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class _Runner:
        def retrieve(self) -> str:
            return ""

        def propose(self, _retrieved: str):
            seen["request"] = seen["ctx"].request
            return []

    monkeypatch.setattr(runtime, "_load_sidecar", lambda _service_dir: None)
    monkeypatch.setattr(runtime, "detect_devskel", lambda _service_dir: None)
    monkeypatch.setattr("builtins.input", lambda: "interactive request")

    def _build_runner(ctx, *, progress=None):
        seen["ctx"] = ctx
        return _Runner()

    monkeypatch.setattr(runtime, "build_runner", _build_runner)

    assert main(tmp_path, []) == 0
    assert seen["request"] == "interactive request"
