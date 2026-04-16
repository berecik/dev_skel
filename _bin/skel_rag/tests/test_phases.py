"""Integration tests for skel-gen-ai generation phases (requires Ollama).

Each test exercises one pipeline phase against a live Ollama instance using
the ``python-django-bolt-skel`` skeleton (the only one that ships an
INTEGRATION_MANIFEST). Tests are ordered Phase 1 → 5 and share a single
generated project via a module-scoped fixture so we only pay the ``skel-gen``
cost once.

Run from the repo root::

    SKEL_VENV/bin/python -m pytest _bin/skel_rag/tests/test_phases.py -v -s

Each Ollama call can take 2-10 minutes per file depending on model size.
The full suite takes ~30-60 minutes with a 32B model. Individual test
timeouts are disabled (use a global ``--timeout`` only if needed).

Skip gracefully when Ollama is unreachable (exit 0, not fail).
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

# ---- path bootstrap --------------------------------------------------------
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
    TargetResult,
    _discover_project_files,
    generate_targets,
    load_integration_manifest,
    load_manifest,
    run_docs_generation,
    run_integration_phase,
    run_test_and_fix_loop,
    discover_siblings,
)
from dev_skel_lib import generate_project, render_agents_template  # noqa: E402

# ---- constants -------------------------------------------------------------
SKEL_NAME = "python-django-bolt-skel"
PROJECT_NAME = "test-phases"
SERVICE_LABEL = "Items API"
ITEM_NAME = "task"
AUTH_TYPE = "jwt"
TEST_DIR = _REPO / "_test_projects" / PROJECT_NAME

# ---- Ollama availability gate ----------------------------------------------
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


# ---- fixtures --------------------------------------------------------------

@pytest.fixture(scope="module")
def ollama_client() -> OllamaClient:
    cfg = OllamaConfig(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
        timeout=600,
    )
    client = OllamaClient(cfg)
    client.verify()
    return client


@pytest.fixture(scope="module")
def generated_project() -> Path:
    """Generate a django-bolt project once for the whole module."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)

    original_cwd = os.getcwd()
    # generate_project expects a leaf name relative to cwd
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

    yield TEST_DIR

    # Cleanup
    if TEST_DIR.exists() and not os.environ.get("KEEP_TEST_PROJECT"):
        shutil.rmtree(TEST_DIR, ignore_errors=True)


@pytest.fixture(scope="module")
def service_subdir(generated_project: Path) -> str:
    """Return the service subdirectory name inside the wrapper."""
    for d in sorted(generated_project.iterdir()):
        if d.is_dir() and d.name not in ("_shared", ".git") and not d.name.startswith("."):
            if (d / "manage.py").exists() or (d / "app").exists():
                return d.name
    pytest.fail("No service directory found in generated project")


@pytest.fixture(scope="module")
def gen_ctx(generated_project: Path, service_subdir: str) -> GenerationContext:
    return GenerationContext(
        skeleton_name=SKEL_NAME,
        skeleton_path=_REPO / "_skels" / SKEL_NAME,
        project_root=generated_project,
        project_name=PROJECT_NAME,
        service_subdir=service_subdir,
        service_label=SERVICE_LABEL,
        item_name=ITEM_NAME,
        auth_type=AUTH_TYPE,
    )


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(_REPO, SKEL_NAME)


@pytest.fixture(scope="module")
def integration_manifest():
    return load_integration_manifest(_REPO, SKEL_NAME)


# ---- Phase 1: per-target generation ----------------------------------------

class TestPhase1PerTargetGeneration:
    """Phase 1 — generate service files via Ollama per-target manifest."""

    def test_manifest_loads(self, manifest):
        assert manifest is not None
        assert len(manifest.targets) > 0
        print(f"\n  Manifest has {len(manifest.targets)} targets")

    def test_generate_targets_produces_files(
        self, ollama_client, manifest, gen_ctx, generated_project
    ):
        progress = io.StringIO()
        results = generate_targets(
            client=ollama_client,
            manifest=manifest,
            ctx=gen_ctx,
            dry_run=False,
            progress=progress,
        )

        assert len(results) > 0, "generate_targets returned no results"
        for r in results:
            assert r.written_to.exists(), f"File not written: {r.written_to}"
            assert r.bytes_written > 0, f"Empty file: {r.written_to}"
            print(f"  + {r.written_to.name} ({r.bytes_written} bytes)")

    def test_generated_files_are_valid_python(self, gen_ctx):
        """All .py files in the service dir should at least parse."""
        import py_compile

        svc_dir = gen_ctx.project_dir
        errors = []
        for f in svc_dir.rglob("*.py"):
            if "__pycache__" in f.parts or ".venv" in f.parts:
                continue
            try:
                py_compile.compile(str(f), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(f"{f.name}: {exc}")
        if errors:
            pytest.fail(f"Syntax errors in generated files:\n" + "\n".join(errors))


# ---- Phase 2: frontend generation (structural only) -------------------------

class TestPhase2FrontendStructure:
    """Phase 2 — verify frontend generation would work structurally.

    We don't generate a full React frontend (needs npm install), but we
    verify the skeleton and manifest infrastructure is sound.
    """

    def test_react_skel_exists(self):
        react_skel = _REPO / "_skels" / "ts-react-skel"
        assert react_skel.is_dir(), "ts-react-skel not found"
        assert (react_skel / "gen").is_file(), "gen script missing"

    def test_react_manifest_loads(self):
        m = load_manifest(_REPO, "ts-react-skel")
        assert m is not None
        assert len(m.targets) > 0
        print(f"\n  ts-react-skel manifest has {len(m.targets)} targets")


# ---- Phase 3: integration ---------------------------------------------------

class TestPhase3Integration:
    """Phase 3 — run the integration phase (sibling discovery + Ollama)."""

    def test_integration_manifest_loads(self, integration_manifest):
        assert integration_manifest is not None
        assert len(integration_manifest.targets) == 3
        assert integration_manifest.fix_timeout_m == 60
        print(f"\n  Integration targets: {[t.path for t in integration_manifest.targets]}")

    def test_discover_siblings(self, generated_project, service_subdir):
        siblings = discover_siblings(generated_project, exclude_slug=service_subdir)
        # Single-service project → no siblings expected
        print(f"\n  Siblings discovered: {len(siblings)}")
        for s in siblings:
            print(f"    - {s.slug} ({s.kind}, {s.tech})")

    def test_run_integration_phase(
        self, ollama_client, integration_manifest, gen_ctx
    ):
        progress = io.StringIO()
        results = run_integration_phase(
            client=ollama_client,
            manifest=integration_manifest,
            ctx=gen_ctx,
            dry_run=False,
            progress=progress,
        )

        assert len(results) > 0, "Integration phase wrote no files"
        for r in results:
            assert r.written_to.exists(), f"File not written: {r.written_to}"
            assert r.bytes_written > 0, f"Empty file: {r.written_to}"
            print(f"  + {r.written_to.name} ({r.bytes_written} bytes)")

    def test_integration_files_are_valid_python(self, gen_ctx):
        import py_compile

        integration_dir = gen_ctx.project_dir / "app" / "integrations"
        test_file = gen_ctx.project_dir / "app" / "tests" / "test_integration.py"

        for f in [test_file] + list(integration_dir.rglob("*.py")):
            if f.exists():
                try:
                    py_compile.compile(str(f), doraise=True)
                except py_compile.PyCompileError as exc:
                    pytest.fail(f"Syntax error in {f.name}: {exc}")


# ---- Phase 4: test-and-fix loop --------------------------------------------

class TestPhase4TestAndFix:
    """Phase 4 — run the test-and-fix loop (bounded to 5 minutes for CI)."""

    def test_discover_project_files(self, gen_ctx):
        files = _discover_project_files(gen_ctx.project_dir)
        assert len(files) > 0, "No fixable files found"
        extensions = {f.written_to.suffix for f in files}
        assert ".py" in extensions
        print(f"\n  Discovered {len(files)} fixable files")

    def test_install_deps(self, gen_ctx):
        """Run install-deps so the venv + pytest are available for ./test."""
        install = gen_ctx.project_dir / "install-deps"
        if not install.exists():
            pytest.skip("install-deps not found")
        proc = subprocess.run(
            ["bash", str(install)],
            cwd=gen_ctx.project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(f"\n  install-deps exit={proc.returncode}")
        if proc.returncode != 0:
            print(f"  stderr: {proc.stderr[-500:]}")
        assert proc.returncode == 0, f"install-deps failed: {proc.stderr[-300:]}"
        assert (gen_ctx.project_dir / ".venv").is_dir(), ".venv not created"

    def test_baseline_tests_run(self, gen_ctx):
        """Verify ./test works before the fix loop (may fail, that's OK)."""
        test_script = gen_ctx.project_dir / "test"
        if not test_script.exists():
            pytest.skip("test script not found")
        proc = subprocess.run(
            ["bash", str(test_script)],
            cwd=gen_ctx.project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(f"\n  ./test exit={proc.returncode}")
        # We don't assert pass — we just verify it runs (not exit 127)
        assert proc.returncode != 127, (
            f"./test returned 127 (command not found). "
            f"stderr: {proc.stderr[-300:]}"
        )

    def test_fix_loop_runs(
        self, ollama_client, gen_ctx, integration_manifest
    ):
        # Use a short timeout for test speed (5 min instead of 60)
        short_manifest = IntegrationManifest(
            skeleton_name=integration_manifest.skeleton_name,
            targets=integration_manifest.targets,
            system_prompt=integration_manifest.system_prompt,
            notes=integration_manifest.notes,
            test_command=integration_manifest.test_command,
            fix_timeout_m=5,
        )

        # Get integration results (files that exist in integration dir)
        integration_dir = gen_ctx.project_dir / "app" / "integrations"
        test_file = gen_ctx.project_dir / "app" / "tests" / "test_integration.py"
        integration_results = []
        for f in [test_file] + list(integration_dir.rglob("*.py")):
            if f.exists():
                from skel_ai_lib import AiTarget

                integration_results.append(
                    TargetResult(
                        target=AiTarget(
                            path=str(f.relative_to(gen_ctx.project_dir)),
                            template=None,
                            prompt="",
                        ),
                        written_to=f,
                        bytes_written=f.stat().st_size,
                    )
                )

        progress = io.StringIO()
        result = run_test_and_fix_loop(
            client=ollama_client,
            ctx=gen_ctx,
            manifest=short_manifest,
            integration_results=integration_results,
            progress=progress,
        )

        output = progress.getvalue()
        print(f"\n{output}")
        assert result is not None, "Fix loop returned None"
        # With deps installed, exit should not be 127 (command not found)
        assert result.returncode != 127, (
            f"Test command returned 127 (not found) — "
            f"install-deps may have failed"
        )
        print(f"  Final result: {'PASS' if result.passed else 'FAIL'} "
              f"(exit {result.returncode})")


# ---- Phase 5: documentation generation -------------------------------------

class TestPhase5DocsGeneration:
    """Phase 5 — generate project documentation via Ollama."""

    def test_docs_generation(self, ollama_client, gen_ctx, generated_project):
        progress = io.StringIO()
        written = run_docs_generation(
            client=ollama_client,
            project_root=generated_project,
            project_name=PROJECT_NAME,
            service_contexts=[gen_ctx],
            dry_run=False,
            progress=progress,
        )

        output = progress.getvalue()
        print(f"\n{output}")
        assert len(written) > 0, "No documentation files written"
        for path in written:
            assert path.exists(), f"Doc file not found: {path}"
            content = path.read_text(encoding="utf-8")
            assert len(content) > 100, f"Doc file too short: {path} ({len(content)} chars)"
            print(f"  + {path.name} ({len(content)} chars)")

    def test_wrapper_readme_is_project_specific(self, generated_project):
        readme = generated_project / "README.md"
        if not readme.exists():
            pytest.skip("README.md not generated")
        content = readme.read_text(encoding="utf-8")
        # Should mention the actual project/service names, not just templates
        assert "django" in content.lower() or "bolt" in content.lower() or PROJECT_NAME in content.lower(), \
            "README doesn't mention the project tech stack"

    def test_agents_md_has_real_paths(self, generated_project):
        agents = generated_project / "AGENTS.md"
        if not agents.exists():
            pytest.skip("AGENTS.md not generated")
        content = agents.read_text(encoding="utf-8")
        assert len(content) > 200, f"AGENTS.md too short ({len(content)} chars)"


# ---- Structural sanity checks -----------------------------------------------

class TestProjectStructure:
    """Verify the generated project has the expected structure."""

    def test_wrapper_scripts_exist(self, generated_project):
        for name in ("run", "test", "build", "stop", "install-deps", "services"):
            script = generated_project / name
            assert script.exists(), f"Wrapper script missing: {name}"
            assert os.access(script, os.X_OK), f"Wrapper script not executable: {name}"

    def test_shared_env(self, generated_project):
        env = generated_project / ".env"
        assert env.exists(), ".env not created"
        content = env.read_text()
        assert "DATABASE_URL" in content
        assert "JWT_SECRET" in content

    def test_service_has_manage_py(self, gen_ctx):
        assert (gen_ctx.project_dir / "manage.py").exists()

    def test_service_has_models(self, gen_ctx):
        models = gen_ctx.project_dir / "app" / "models.py"
        assert models.exists()
        content = models.read_text()
        assert "Item" in content
        assert "ReactState" in content
        assert "JSONField" in content
