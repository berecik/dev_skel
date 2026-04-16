"""End-to-end Phase 4 test — generate, install, run integration tests.

This test exercises the full pipeline:
  Phase 1: Generate django-bolt service via Ollama per-target manifest
  Phase 3: Run integration phase (generates test_integration.py)
  Phase 4: Install deps, run integration tests, verify they pass

The test is intentionally a single large function so the project is
generated once and the phases are tested in sequence. Uses a 10-minute
fix loop timeout for CI.

Run::

    SKEL_VENV/bin/python -m pytest _bin/skel_rag/tests/test_phase4_e2e.py -v -s

Requires Ollama running with the default model (~30 min total).
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[2]
_REPO = _BIN.parent
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from skel_ai_lib import (  # noqa: E402
    GenerationContext,
    IntegrationManifest,
    OllamaClient,
    OllamaConfig,
    OllamaError,
    generate_targets,
    load_integration_manifest,
    load_manifest,
    run_integration_phase,
    run_test_and_fix_loop,
    discover_siblings,
)
from dev_skel_lib import generate_project, render_agents_template  # noqa: E402

SKEL_NAME = "python-django-bolt-skel"
PROJECT_NAME = "test-phase4"
SERVICE_LABEL = "Items API"
ITEM_NAME = "task"
AUTH_TYPE = "jwt"
TEST_DIR = _REPO / "_test_projects" / PROJECT_NAME

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:32b")


def _ollama_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=5):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=f"Ollama not reachable at {OLLAMA_BASE_URL}",
)


def test_phase4_full_pipeline():
    """Generate → install-deps → run integration tests → fix loop."""

    # ---- Setup: clean project dir ----------------------------------------
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)

    original_cwd = os.getcwd()

    # ---- Phase 1: Generate project + per-target overlay ------------------
    print("\n===== Phase 1: Generate project =====")
    os.chdir(TEST_DIR.parent)
    try:
        service_subdir = generate_project(
            root=_REPO,
            skel_name=SKEL_NAME,
            proj_name=PROJECT_NAME,
            service_name=SERVICE_LABEL,
        )
    finally:
        os.chdir(original_cwd)

    render_agents_template(
        target=TEST_DIR,
        service_subdir=service_subdir,
        skeleton_name=SKEL_NAME,
        project_name=PROJECT_NAME,
    )

    ctx = GenerationContext(
        skeleton_name=SKEL_NAME,
        skeleton_path=_REPO / "_skels" / SKEL_NAME,
        project_root=TEST_DIR,
        project_name=PROJECT_NAME,
        service_subdir=service_subdir,
        service_label=SERVICE_LABEL,
        item_name=ITEM_NAME,
        auth_type=AUTH_TYPE,
    )

    cfg = OllamaConfig(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
        timeout=600,
    )
    client = OllamaClient(cfg)
    client.verify()

    manifest = load_manifest(_REPO, SKEL_NAME)
    progress = io.StringIO()
    results = generate_targets(
        client=client,
        manifest=manifest,
        ctx=ctx,
        dry_run=False,
        progress=progress,
    )
    print(progress.getvalue())
    assert len(results) > 0, "Phase 1 produced no files"
    for r in results:
        assert r.written_to.exists()
    print(f"  Phase 1: {len(results)} files generated")

    # ---- Phase 3: Integration (generates test_integration.py) ------------
    print("\n===== Phase 3: Integration =====")
    int_manifest = load_integration_manifest(_REPO, SKEL_NAME)
    assert int_manifest is not None

    ctx.siblings = discover_siblings(TEST_DIR, exclude_slug=service_subdir)
    progress = io.StringIO()
    int_results = run_integration_phase(
        client=client,
        manifest=int_manifest,
        ctx=ctx,
        dry_run=False,
        progress=progress,
    )
    print(progress.getvalue())
    assert len(int_results) > 0, "Integration phase produced no files"
    test_file = ctx.project_dir / "app" / "tests" / "test_integration.py"
    assert test_file.exists(), "test_integration.py not generated"
    print(f"  Phase 3: {len(int_results)} integration files")

    # ---- Install deps ----------------------------------------------------
    print("\n===== Installing deps =====")
    proc = subprocess.run(
        ["bash", str(ctx.project_dir / "install-deps")],
        cwd=ctx.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"install-deps failed:\n{proc.stderr[-500:]}"
    assert (ctx.project_dir / ".venv").is_dir()
    print("  install-deps: OK")

    # ---- Baseline: run all skel tests (should pass) ----------------------
    print("\n===== Baseline test run =====")
    proc = subprocess.run(
        ["bash", str(ctx.project_dir / "test"), "-v"],
        cwd=ctx.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(f"  Baseline exit={proc.returncode}")
    if proc.stdout:
        # Print last 30 lines of test output
        lines = proc.stdout.strip().split("\n")
        for line in lines[-30:]:
            print(f"    {line}")

    # ---- Run integration tests specifically ------------------------------
    print("\n===== Integration tests =====")
    proc = subprocess.run(
        ["bash", str(ctx.project_dir / "test"),
         "app/tests/test_integration.py", "-v"],
        cwd=ctx.project_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(f"  Integration tests exit={proc.returncode}")
    if proc.stdout:
        lines = proc.stdout.strip().split("\n")
        for line in lines[-20:]:
            print(f"    {line}")

    if proc.returncode == 0:
        print("\n  ALL INTEGRATION TESTS PASSED — no fix loop needed!")
    else:
        # ---- Phase 4: Fix loop (10 min timeout for CI) -------------------
        print("\n===== Phase 4: Fix loop =====")
        fix_manifest = IntegrationManifest(
            skeleton_name=int_manifest.skeleton_name,
            targets=int_manifest.targets,
            system_prompt=int_manifest.system_prompt,
            notes=int_manifest.notes,
            test_command=int_manifest.test_command,
            fix_timeout_m=10,
        )

        progress = io.StringIO()
        result = run_test_and_fix_loop(
            client=client,
            ctx=ctx,
            manifest=fix_manifest,
            integration_results=int_results,
            progress=progress,
        )
        print(progress.getvalue())
        print(f"  Fix loop final: {'PASS' if result.passed else 'FAIL'} "
              f"(exit {result.returncode})")

        # Run integration tests one final time to report
        proc = subprocess.run(
            ["bash", str(ctx.project_dir / "test"),
             "app/tests/test_integration.py", "-v"],
            cwd=ctx.project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.stdout:
            lines = proc.stdout.strip().split("\n")
            for line in lines[-20:]:
                print(f"    {line}")

    # ---- Final assertion -------------------------------------------------
    assert proc.returncode == 0, (
        f"Integration tests still failing after fix loop.\n"
        f"Exit: {proc.returncode}\n"
        f"Last output:\n{proc.stdout[-1000:]}\n"
        f"Stderr:\n{proc.stderr[-500:]}"
    )

    # ---- Cleanup (unless KEEP_TEST_PROJECT is set) -----------------------
    if not os.environ.get("KEEP_TEST_PROJECT"):
        shutil.rmtree(TEST_DIR, ignore_errors=True)
