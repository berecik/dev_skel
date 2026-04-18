"""Shared helpers for the <frontend> + <backend> cross-stack integration tests.

`_bin/skel-test-react-django-bolt`,
`_bin/skel-test-react-fastapi`,
`_bin/skel-test-flutter-django-bolt`, and
`_bin/skel-test-flutter-fastapi` all do the same thing:

1. Generate a wrapper containing the backend skeleton + a frontend
   skeleton (React or Flutter).
2. Rewrite ``BACKEND_URL`` in the wrapper ``.env`` to a non-conflicting
   port. For React, this triggers a Vite re-build that bakes the new
   URL into the bundle. For Flutter, the wrapper ``.env`` is also
   re-copied into the project's bundled ``.env`` asset (since the gen
   script copied the OLD value during scaffold) and ``flutter build
   web`` produces a fresh asset bundle that includes the updated env.
3. Inspect the build output to confirm the URL + canonical endpoint
   paths are bundled correctly (React: dist/assets/*.js; Flutter:
   build/web/assets/.env + the compiled main.dart.js).
4. Run any backend-specific setup (django-bolt → makemigrations +
   migrate; fastapi → nothing because the wrapper-shared API
   auto-creates tables).
5. Start the backend server in the background on the chosen port.
6. Exercise the canonical 9 sub-step ``register → login → CRUD →
   complete → reject anonymous → reject invalid token`` flow over real
   HTTP. The exercise hits the BACKEND, not the frontend, so it works
   identically for React and Flutter.
7. Stop the server cleanly and clean up the wrapper.

This module exposes:

* :class:`BackendSpec` — declarative description of a backend (skel
  name, service display name, server argv, optional pre-server setup).
* :class:`Frontend` — declarative description of a frontend (skel
  name, toolchain probe, build callable, build-output inspector).
* :data:`REACT_FRONTEND` and :data:`FLUTTER_FRONTEND` — pre-built
  instances for the two shipped frontends.
* :func:`run_frontend_backend_integration` — generic driver that
  runs the full 7-step flow for any (frontend, backend) pair.
* :func:`run_react_backend_integration` — backwards-compatible alias
  for the React-only entrypoint that the older FastAPI/django-bolt
  scripts call. New scripts should call
  :func:`run_frontend_backend_integration` directly with an explicit
  ``frontend=`` argument.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
#  Constants reused by every backend test
# --------------------------------------------------------------------------- #


EXIT_OK = 0
EXIT_FAIL = 1
EXIT_SETUP = 2

# Legacy constants kept for backwards compat with the React-only
# `run_react_backend_integration` shim (and any third-party scripts).
# New code should pull the equivalent values off a :class:`Frontend`
# instance — see :data:`REACT_FRONTEND` below.
FRONTEND_SKEL = "ts-react-skel"
FRONTEND_SERVICE_NAME = "Web UI"

DEFAULT_PORT = 18765
DEFAULT_STARTUP_TIMEOUT = 60

TEST_USERNAME = "react-integration-user"
TEST_PASSWORD = "react-integration-pw-12345"
TEST_EMAIL = "react-test@example.com"
TEST_ITEM_NAME = "react-integration-test-item"
TEST_ITEM_DESCRIPTION = "Created by the cross-stack integration test"
TEST_CATEGORY_NAME = "react-integration-test-category"
TEST_CATEGORY_DESCRIPTION = "Category created by the cross-stack integration test"


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def chdir(path: Path):
    """`os.chdir` context manager that survives the cwd being deleted."""

    saved = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        try:
            os.chdir(saved)
        except FileNotFoundError:
            os.chdir(Path.home())


def have_node() -> bool:
    return bool(shutil.which("node")) and bool(shutil.which("npm"))


def http_request(
    method: str,
    url: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10,
) -> Tuple[int, Any]:
    """Tiny stdlib HTTP client. Returns ``(status_code, parsed_body)``.

    Caught HTTPError responses are surfaced through the same return
    shape so callers can ``assert status == 401`` without try/except.
    """

    data: Optional[bytes] = None
    req_headers: Dict[str, str] = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        req_headers.setdefault("Content-Type", "application/json")
        data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(
        url, data=data, headers=req_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""

    parsed: Any
    if not raw:
        parsed = None
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
    return status, parsed


def wait_for_server(url: str, timeout_s: int) -> bool:
    """Poll ``url`` until any HTTP response is returned (incl. 4xx/5xx).

    Used right after spawning the backend subprocess to know when its
    HTTP layer has finished binding. We accept any HTTP response — only
    connection errors / timeouts mean we should keep waiting.
    """

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(
                url,
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=2) as resp:
                resp.read()
            return True
        except urllib.error.HTTPError:
            return True  # any HTTP response means the server is up
        except (urllib.error.URLError, ConnectionError, OSError, TimeoutError):
            time.sleep(0.5)
    return False


def update_wrapper_env(env_path: Path, key: str, value: str) -> None:
    """Update or append ``key=value`` in a wrapper-style ``.env`` file."""

    if not env_path.is_file():
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines()
    new_lines: List[str] = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def collect_react_bundle(frontend_dir: Path) -> str:
    """Concatenate every JS file under ``dist/assets/`` into one string."""

    dist_assets = frontend_dir / "dist" / "assets"
    if not dist_assets.is_dir():
        raise AssertionError(
            f"React build did not produce dist/assets/ at {dist_assets}"
        )
    js_files = sorted(dist_assets.glob("*.js"))
    if not js_files:
        raise AssertionError(
            f"No JavaScript files found under {dist_assets}"
        )
    chunks: List[str] = []
    for js in js_files:
        try:
            chunks.append(js.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            raise AssertionError(f"Could not read {js}: {exc}")
    return "\n".join(chunks)


def generate_one_service(
    *,
    repo_root: Path,
    wrapper_dir: Path,
    skeleton: str,
    service_label: str,
) -> str:
    """Generate one service into ``wrapper_dir``. Returns the service slug."""

    # Imported lazily so library users that only need the helpers
    # (e.g. unit-test runners) do not pay the dev_skel_lib import cost.
    from dev_skel_lib import generate_project, render_agents_template

    with chdir(wrapper_dir.parent):
        slug = generate_project(
            root=repo_root,
            skel_name=skeleton,
            proj_name=wrapper_dir.name,
            service_name=service_label,
        )
    render_agents_template(
        target=wrapper_dir,
        service_subdir=slug,
        skeleton_name=skeleton,
        project_name=wrapper_dir.name,
    )
    return slug


# --------------------------------------------------------------------------- #
#  Backend lifecycle
# --------------------------------------------------------------------------- #


@dataclass
class BackendSpec:
    """Description of one backend skeleton from the test runner's POV."""

    skeleton: str
    service_name: str
    # Argv used to start the server in the background. The runner
    # substitutes ``{port}`` and ``{host}`` literally before spawning,
    # so the spec stays declarative. The first element is the executable
    # (typically a path to the per-service venv python).
    server_argv_template: List[str]
    # Optional list of subprocess argv lists to run after the wrapper is
    # generated and before the server starts (e.g. Django migrations).
    # Each entry is `(label, argv)`. Same `{port}` / `{host}` template
    # substitution is applied.
    pre_server_setup: List[Tuple[str, List[str]]] = field(default_factory=list)
    # Extra env vars to inject into the server subprocess (the wrapper
    # `.env` is already sourced by the per-service settings module, but
    # explicit env wins).
    extra_env: Dict[str, str] = field(default_factory=dict)


def _format_argv(template: Sequence[str], host: str, port: int) -> List[str]:
    return [item.format(host=host, port=port) for item in template]


def run_backend_setup(
    *,
    backend_dir: Path,
    spec: BackendSpec,
    host: str,
    port: int,
) -> None:
    """Run every entry in ``spec.pre_server_setup`` from ``backend_dir``.

    The setup commands inherit ``spec.extra_env`` (so ``migrate``,
    ``schema-load``, etc. see the same ``DATABASE_URL`` the server
    will). Without this, a per-test ``DATABASE_URL`` override would
    only reach the spawned server process, leaving migrations to
    target the skeleton's default DB file — and the cross-stack
    request would then hit empty tables.
    """

    setup_env = os.environ.copy()
    setup_env.update(spec.extra_env)

    for label, argv_template in spec.pre_server_setup:
        argv = _format_argv(argv_template, host, port)
        result = subprocess.run(
            argv,
            cwd=backend_dir,
            env=setup_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{label} failed (exit {result.returncode}): "
                f"{result.stderr.strip()[-2000:]}"
            )
        last = (result.stdout.strip().splitlines()[-1:] or ["(no output)"])[0]
        print(f"  ✓ {label}: {last}")


# --------------------------------------------------------------------------- #
#  Frontend abstraction
# --------------------------------------------------------------------------- #
#
# Each cross-stack integration test is parameterised by a `Frontend` and
# a `BackendSpec`. The `Frontend` captures the per-frontend bits the
# generic driver does not know about:
#
#   - which skel + service display name to generate
#   - how to detect that the toolchain is installed (so unsupported
#     hosts skip cleanly with EXIT_SETUP)
#   - what to do AFTER the wrapper `.env` has been rewritten (e.g.
#     re-build the bundle, or re-copy the env into a runtime asset)
#   - how to inspect the build artifacts to confirm the new
#     `BACKEND_URL` actually got baked / bundled in
#
# Two pre-built instances ship today: :data:`REACT_FRONTEND` and
# :data:`FLUTTER_FRONTEND`. New frontends only need to add a third
# instance and a one-liner driver script that calls
# :func:`run_frontend_backend_integration` with it.


@dataclass
class Frontend:
    """Per-frontend hooks consumed by :func:`run_frontend_backend_integration`."""

    name: str
    skel: str
    service_name: str
    # Human-readable name of the missing tooling, used in skip messages.
    toolchain_label: str
    # Returns True when the host can build this frontend (e.g. Node + npm
    # for React, the Flutter SDK for Flutter).
    toolchain_probe: Callable[[], bool]
    # Called after the wrapper has been generated AND `BACKEND_URL` has
    # been rewritten in `<wrapper>/.env`. Receives `(wrapper, frontend_dir,
    # backend_url)` and is expected to (re)produce the build artifacts
    # the next step inspects. May raise on failure.
    build: Callable[[Path, Path, str], None]
    # Inspects the freshly built artifacts and returns a list of
    # `(label, value)` pairs that the runner asserts are present in the
    # bundle / asset. Raises AssertionError on missing strings.
    inspect_bundle: Callable[[Path, str, Optional[Dict[str, str]]], None]
    # Optional: invoked AFTER the backend is up + the Python pre-flight
    # has confirmed the items API works. Runs the frontend's OWN test
    # runner (vitest for React, `flutter test` for Flutter) against a
    # smoke file that imports the real client code and exercises the
    # full 9-step flow over real HTTP. Receives `(frontend_dir,
    # backend_url)` and raises on any failure. ``None`` means "skip
    # the frontend smoke step" (used by tests that only care about
    # the bundle inspection).
    frontend_smoke: Optional[Callable[[Path, str], None]] = None
    # Optional: invoked AFTER the frontend_smoke succeeds. Runs
    # Playwright (or an equivalent browser-level E2E runner) against
    # the production-built frontend served by `vite preview` (React)
    # or an equivalent. Receives `(frontend_dir, backend_url, port)`
    # so the runner can compute a unique preview port. Raises on
    # failure. ``None`` means "no E2E step".
    e2e: Optional[Callable[[Path, str, int], None]] = None


def _react_build(wrapper: Path, frontend_dir: Path, backend_url: str) -> None:
    """`npm run build` against ``frontend_dir`` so Vite re-bakes the env."""

    started = time.monotonic()
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend_dir,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        tail = result.stderr.strip()[-2000:]
        raise RuntimeError(f"npm run build failed:\n{tail}")
    print(f"  ✓ React build OK in {time.monotonic() - started:.1f}s")


def _react_inspect_bundle(
    frontend_dir: Path,
    backend_url: str,
    extra: Optional[Dict[str, str]] = None,
) -> None:
    """Concatenate `dist/assets/*.js` and assert the canonical strings."""

    bundle = collect_react_bundle(frontend_dir)
    expected: Dict[str, str] = {
        "BACKEND_URL value": backend_url,
        "items endpoint path": "/api/items",
        "categories endpoint path": "/api/categories",
        "auth login path": "/api/auth/login",
        "Bearer header": "Bearer",
        "JWT issuer (devskel)": "devskel",
    }
    if extra:
        expected.update(extra)
    missing = [
        label for label, needle in expected.items() if needle not in bundle
    ]
    if missing:
        raise AssertionError(
            f"React bundle is missing expected strings: {missing}"
        )
    print(f"  ✓ bundle ({len(bundle)} chars) contains all expected strings")
    for label, needle in expected.items():
        print(f"     · {label}: '{needle}'")


def _flutter_build(wrapper: Path, frontend_dir: Path, backend_url: str) -> None:
    """`flutter pub get` + `flutter build web` against ``frontend_dir``.

    No env patching here — the test driver exports
    ``SKEL_BACKEND_URL`` BEFORE invoking ``gen``, ``common-wrapper.sh``
    propagates it into ``<wrapper>/.env`` at scaffold time, and the
    Flutter ``gen`` script's "copy ``<wrapper>/.env`` into
    ``<frontend>/.env``" step picks up the correct value. By the time
    we get here, the bundled ``.env`` asset is already wired with the
    test backend URL — exactly what an end user would see by setting
    ``SKEL_BACKEND_URL`` themselves before generating a wrapper.
    """

    started = time.monotonic()
    pub_get = subprocess.run(
        ["flutter", "pub", "get"],
        cwd=frontend_dir,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if pub_get.returncode != 0:
        tail = (pub_get.stdout + pub_get.stderr).strip()[-2000:]
        raise RuntimeError(f"flutter pub get failed:\n{tail}")

    build = subprocess.run(
        ["flutter", "build", "web", "--no-tree-shake-icons"],
        cwd=frontend_dir,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if build.returncode != 0:
        tail = (build.stdout + build.stderr).strip()[-2000:]
        raise RuntimeError(f"flutter build web failed:\n{tail}")
    print(f"  ✓ Flutter web build OK in {time.monotonic() - started:.1f}s")


def _flutter_inspect_bundle(
    frontend_dir: Path,
    backend_url: str,
    extra: Optional[Dict[str, str]] = None,
) -> None:
    """Verify the bundled `.env` asset and the compiled main.dart.js.

    Flutter ships the env at runtime via `flutter_dotenv`, so the
    primary check is that `build/web/assets/.env` contains the
    rewritten `BACKEND_URL`. As a defence-in-depth check we also grep
    the compiled `main.dart.js` for the canonical endpoint paths so a
    silent dotenv rename or asset-bundle regression is caught early.
    """

    web_dist = frontend_dir / "build" / "web"
    if not web_dist.is_dir():
        raise AssertionError(
            f"flutter build did not produce build/web/ at {web_dist}"
        )

    # The bundled .env asset can land at one of two paths depending on
    # the Flutter version. Check both and use whichever exists.
    env_candidates = [
        web_dist / "assets" / ".env",
        web_dist / "assets" / "assets" / ".env",
    ]
    env_path = next((p for p in env_candidates if p.is_file()), None)
    if env_path is None:
        raise AssertionError(
            "Bundled .env asset missing — looked at: "
            + ", ".join(str(p) for p in env_candidates)
        )

    env_text = env_path.read_text(encoding="utf-8", errors="replace")
    if f"BACKEND_URL={backend_url}" not in env_text:
        raise AssertionError(
            f"Bundled .env asset at {env_path} does not contain "
            f"BACKEND_URL={backend_url}\n"
            f"  contents (truncated): {env_text[:400]!r}"
        )
    print(f"  ✓ bundled .env asset at {env_path.relative_to(frontend_dir)}")
    print(f"     · BACKEND_URL value: '{backend_url}'")

    # Compiled Dart bundle. main.dart.js is the canonical name produced
    # by `flutter build web`; the AssetManifest references it from
    # index.html. We do NOT assert on its size — only that the canonical
    # endpoint strings the dart code uses are present.
    main_js = web_dist / "main.dart.js"
    if not main_js.is_file():
        raise AssertionError(f"main.dart.js missing at {main_js}")
    bundle = main_js.read_text(encoding="utf-8", errors="replace")

    expected: Dict[str, str] = {
        "items endpoint path": "/api/items",
        "auth login path": "/api/auth/login",
        "Bearer header": "Bearer",
    }
    # Categories check — only when the Flutter frontend ships the client
    # (will be added when flutter-skel gains categories_client.dart).
    if extra:
        expected.update(extra)
    missing = [
        label for label, needle in expected.items() if needle not in bundle
    ]
    if missing:
        raise AssertionError(
            f"main.dart.js is missing expected strings: {missing}"
        )
    print(
        f"  ✓ main.dart.js ({len(bundle)} chars) contains all expected strings"
    )
    for label, needle in expected.items():
        print(f"     · {label}: '{needle}'")


def have_flutter() -> bool:
    return bool(shutil.which("flutter"))


# --------------------------------------------------------------------------- #
#  Frontend smoke runners — exercise the REAL client code against the live
#  backend, not Python's stdlib http. The Python `exercise_items_api` runs
#  first as a pre-flight (cheap, fast feedback when the backend is broken);
#  these run AFTER it succeeds and prove the *frontend's* code path works.
# --------------------------------------------------------------------------- #


def _react_smoke(frontend_dir: Path, backend_url: str) -> None:
    """Run the React vitest smoke test that imports the real items.ts.

    Invokes ``npx vitest run src/cross-stack.smoke.test.ts`` with
    ``RUN_CROSS_STACK_SMOKE=1`` and ``BACKEND_URL=...`` so the test
    file's gate fires. The file uses the ``.test.ts`` infix so vitest's
    default glob picks it up; the ``describe.skipIf(!RUN_SMOKE)`` gate
    inside the file makes ``npm test`` no-op when no backend is running.
    """

    smoke_file = frontend_dir / "src" / "cross-stack.smoke.test.ts"
    if not smoke_file.is_file():
        raise RuntimeError(
            f"React smoke file missing at {smoke_file} — the merge "
            "script needs an OVERWRITE_PATTERN entry for it."
        )

    env = os.environ.copy()
    env["RUN_CROSS_STACK_SMOKE"] = "1"
    env["BACKEND_URL"] = backend_url
    # Avoid triggering CI heuristics inside vitest that might dim
    # output or rotate the reporter — we want plain stdout for the
    # parent runner to capture.
    env["CI"] = "1"

    started = time.monotonic()
    result = subprocess.run(
        [
            "npx",
            "--no-install",
            "vitest",
            "run",
            "src/cross-stack.smoke.test.ts",
        ],
        cwd=frontend_dir,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip()[-3000:]
        raise AssertionError(
            f"React smoke (vitest) failed (exit {result.returncode}):\n{tail}"
        )
    print(
        f"  ✓ React vitest smoke passed in {time.monotonic() - started:.1f}s"
    )
    # Surface the test summary line so the parent CI log shows
    # what actually ran (useful for debugging "skipped" runs that
    # silently produce 0 assertions).
    last_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("stderr")
    ][-6:]
    for line in last_lines:
        print(f"     {line}")


def _flutter_e2e(frontend_dir: Path, backend_url: str, port: int) -> None:
    """Run the Flutter widget-driven E2E test against the live backend.

    Equivalent to React's ``_react_e2e``: drives the full production
    widget tree (`DevSkelApp` + `LoginScreen` + `HomeScreen` + form +
    list + persistent filter) instead of just the ``ItemsClient`` and
    ``StateApi`` pair the smoke test exercises.

    The runner gates the test file with two env vars so a developer
    running ``flutter test`` standalone never accidentally hits the
    backend:

      * ``RUN_CROSS_STACK_E2E=1`` — file-level gate.
      * ``BACKEND_URL=...`` — live URL to register / auth / CRUD against.

    We invoke ``flutter test`` (not ``flutter drive``) so no
    chromedriver / browser install is needed; the widget tree runs in
    the host VM via ``WidgetTester`` and makes real HTTP calls.
    """

    e2e_file = frontend_dir / "test" / "cross_stack_e2e_test.dart"
    if not e2e_file.is_file():
        raise RuntimeError(
            f"Flutter E2E file missing at {e2e_file} — the merge "
            "script needs an OVERWRITE_PATTERN entry for it."
        )

    env = os.environ.copy()
    env["RUN_CROSS_STACK_E2E"] = "1"
    env["BACKEND_URL"] = backend_url

    started = time.monotonic()
    result = subprocess.run(
        [
            "flutter",
            "test",
            "test/cross_stack_e2e_test.dart",
            "--reporter",
            "compact",
        ],
        cwd=frontend_dir,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip()[-3000:]
        raise AssertionError(
            f"Flutter E2E (flutter test) failed (exit {result.returncode}):\n{tail}"
        )
    print(
        f"  ✓ Flutter widget E2E passed in {time.monotonic() - started:.1f}s"
    )
    summary_lines = [
        line for line in result.stdout.splitlines() if line.strip()
    ][-4:]
    for line in summary_lines:
        print(f"     {line}")


def _flutter_smoke(frontend_dir: Path, backend_url: str) -> None:
    """Run the Flutter smoke test that imports the real ItemsClient.

    Invokes ``flutter test test/cross_stack_smoke_test.dart`` with
    ``RUN_CROSS_STACK_SMOKE=1`` and ``BACKEND_URL=...`` so the test
    file's gate fires. We point ``flutter test`` at the file
    explicitly so widget_test.dart (which pumps the LoginScreen with
    a mock client) does NOT also run — the smoke wants the live
    backend, not the mock.
    """

    smoke_file = frontend_dir / "test" / "cross_stack_smoke_test.dart"
    if not smoke_file.is_file():
        raise RuntimeError(
            f"Flutter smoke file missing at {smoke_file} — the merge "
            "script needs an OVERWRITE_PATTERN entry for it."
        )

    env = os.environ.copy()
    env["RUN_CROSS_STACK_SMOKE"] = "1"
    env["BACKEND_URL"] = backend_url

    started = time.monotonic()
    result = subprocess.run(
        [
            "flutter",
            "test",
            "test/cross_stack_smoke_test.dart",
            "--reporter",
            "compact",
        ],
        cwd=frontend_dir,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip()[-3000:]
        raise AssertionError(
            f"Flutter smoke (flutter test) failed (exit {result.returncode}):\n{tail}"
        )
    print(
        f"  ✓ Flutter test smoke passed in {time.monotonic() - started:.1f}s"
    )
    # Surface the trailing test summary so the parent CI log shows
    # the actual count (the compact reporter ends with `+N: All tests
    # passed!`).
    summary_lines = [
        line for line in result.stdout.splitlines() if line.strip()
    ][-4:]
    for line in summary_lines:
        print(f"     {line}")


def _react_e2e(frontend_dir: Path, backend_url: str, port: int) -> None:
    """Launch ``vite preview`` + Playwright against the production build.

    1. Starts ``npx vite preview`` in the background on ``preview_port``
       (= ``port + 1000`` so the preview server doesn't collide with
       the backend or the dev server).
    2. Waits for the preview server to become reachable.
    3. Runs ``npx playwright test`` with ``PLAYWRIGHT_BASE_URL`` pointing
       at the preview server and ``BACKEND_URL`` pointing at the live
       backend (needed by the register helper inside the spec).
    4. Kills the preview server.

    Requires ``@playwright/test`` and Chromium to be installed in the
    generated project (the ``gen`` script handles both).
    """

    preview_port = port + 1000
    preview_url = f"http://127.0.0.1:{preview_port}"

    # Check Playwright is installed.
    pw_config = frontend_dir / "playwright.config.ts"
    if not pw_config.is_file():
        raise RuntimeError(
            f"playwright.config.ts missing at {pw_config} — the merge "
            "script needs an OVERWRITE_PATTERN entry for it."
        )

    # Start vite preview in the background.
    preview_env = os.environ.copy()
    preview_log_path = frontend_dir / "e2e-preview-server.log"
    preview_log = open(preview_log_path, "wb")
    preview_proc = subprocess.Popen(
        ["npx", "vite", "preview", "--port", str(preview_port), "--host", "127.0.0.1"],
        cwd=frontend_dir,
        stdout=preview_log,
        stderr=subprocess.STDOUT,
        env=preview_env,
    )

    try:
        # Wait for the preview server to become reachable.
        if not wait_for_server(preview_url, timeout_s=30):
            raise AssertionError(
                f"vite preview did not start on {preview_url} within 30s. "
                f"Log: {preview_log_path}"
            )
        print(f"  ✓ vite preview server is up on {preview_url}")

        # Run Playwright.
        pw_env = os.environ.copy()
        pw_env["PLAYWRIGHT_BASE_URL"] = preview_url
        pw_env["BACKEND_URL"] = backend_url
        pw_env["CI"] = "1"

        started = time.monotonic()
        result = subprocess.run(
            ["npx", "playwright", "test", "--reporter=list"],
            cwd=frontend_dir,
            env=pw_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            tail = (result.stdout + result.stderr).strip()[-3000:]
            raise AssertionError(
                f"Playwright E2E failed (exit {result.returncode}):\n{tail}"
            )
        print(
            f"  ✓ Playwright E2E passed in {time.monotonic() - started:.1f}s"
        )
        summary = [
            line for line in result.stdout.splitlines() if line.strip()
        ][-4:]
        for line in summary:
            print(f"     {line}")

    finally:
        # Kill the preview server.
        if preview_proc.poll() is None:
            preview_proc.terminate()
            try:
                preview_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                preview_proc.kill()
                try:
                    preview_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
        try:
            preview_log.close()
        except OSError:
            pass


REACT_FRONTEND = Frontend(
    name="React",
    skel=FRONTEND_SKEL,
    service_name=FRONTEND_SERVICE_NAME,
    toolchain_label="Node.js / npm",
    toolchain_probe=have_node,
    build=_react_build,
    inspect_bundle=_react_inspect_bundle,
    frontend_smoke=_react_smoke,
    e2e=_react_e2e,
)

FLUTTER_FRONTEND = Frontend(
    name="Flutter",
    skel="flutter-skel",
    service_name="Mobile UI",
    toolchain_label="Flutter SDK",
    toolchain_probe=have_flutter,
    build=_flutter_build,
    inspect_bundle=_flutter_inspect_bundle,
    frontend_smoke=_flutter_smoke,
    e2e=_flutter_e2e,
)


# --------------------------------------------------------------------------- #
#  9-step HTTP exercise
# --------------------------------------------------------------------------- #


def exercise_categories_api(
    backend_url: str,
    auth_headers: Dict[str, str],
) -> int:
    """Exercise the /api/categories CRUD lifecycle.

    Returns the id of a category created during the exercise (used by
    the caller to create an item WITH a category_id and verify the FK
    round-trips).
    """

    print()
    print("Exercising the categories API flow...")

    # C1: create a category
    status, body = http_request(
        "POST",
        f"{backend_url}/api/categories",
        body={
            "name": TEST_CATEGORY_NAME,
            "description": TEST_CATEGORY_DESCRIPTION,
        },
        headers=auth_headers,
    )
    assert status == 201, (
        f"POST /api/categories expected 201, got {status}: {body}"
    )
    cat_id = body.get("id") if isinstance(body, dict) else None
    assert cat_id, f"create category response missing id: {body}"
    assert body.get("name") == TEST_CATEGORY_NAME
    print(
        f"  ✓ POST /api/categories → 201 (id={cat_id}, "
        f"name='{body.get('name')}')"
    )

    # C2: list categories
    status, body = http_request(
        "GET",
        f"{backend_url}/api/categories",
        headers=auth_headers,
    )
    assert status == 200
    cats = body if isinstance(body, list) else (
        (body.get("results") or body.get("items") or []) if isinstance(body, dict) else []
    )
    cat_names = [c.get("name") for c in cats if isinstance(c, dict)]
    assert TEST_CATEGORY_NAME in cat_names, (
        f"new category not in list: {cat_names}"
    )
    print(f"  ✓ GET /api/categories → 200 (count={len(cats)})")

    # C3: retrieve by id
    status, body = http_request(
        "GET",
        f"{backend_url}/api/categories/{cat_id}",
        headers=auth_headers,
    )
    assert status == 200
    assert body.get("id") == cat_id
    assert body.get("name") == TEST_CATEGORY_NAME
    print(f"  ✓ GET /api/categories/{cat_id} → 200 (round-trip OK)")

    # C4: update
    status, body = http_request(
        "PUT",
        f"{backend_url}/api/categories/{cat_id}",
        body={
            "name": TEST_CATEGORY_NAME + "-updated",
            "description": "Updated by integration test",
        },
        headers=auth_headers,
    )
    assert status == 200, (
        f"PUT /api/categories/{cat_id} expected 200, got {status}: {body}"
    )
    assert body.get("name") == TEST_CATEGORY_NAME + "-updated"
    print(f"  ✓ PUT /api/categories/{cat_id} → 200 (updated)")

    # C5: anonymous request rejected
    status, _body = http_request(
        "GET", f"{backend_url}/api/categories",
    )
    assert status in (401, 403), (
        f"anonymous GET /api/categories expected 401/403, got {status}"
    )
    print(
        f"  ✓ GET /api/categories without token → {status} "
        f"(JWT enforcement works)"
    )

    return cat_id


def exercise_items_api(backend_url: str) -> None:
    """Run the canonical register → login → CRUD → categories → reject flow.

    Every per-backend test calls this against its own running backend.
    Raises :class:`AssertionError` on any sub-step failure so the
    surrounding script can print + clean up.
    """

    print()
    print("Exercising the cross-stack items API flow...")

    # Sub-step 1: register
    status, body = http_request(
        "POST",
        f"{backend_url}/api/auth/register",
        body={
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        },
    )
    assert status == 201, f"register expected 201, got {status}: {body}"
    user_payload = body.get("user", {}) if isinstance(body, dict) else {}
    user_id = user_payload.get("id")
    assert user_id, f"register response missing user.id: {body}"
    print(f"  ✓ POST /api/auth/register → 201 (user_id={user_id})")

    # Sub-step 2: login → JWT
    status, body = http_request(
        "POST",
        f"{backend_url}/api/auth/login",
        body={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert status == 200, f"login expected 200, got {status}: {body}"
    token = (
        (body.get("access") or body.get("token"))
        if isinstance(body, dict)
        else None
    )
    assert token, f"login response missing access token: {body}"
    print(
        f"  ✓ POST /api/auth/login → 200 (jwt len={len(token)}, "
        f"first 12 chars='{token[:12]}...')"
    )

    auth_headers = {"Authorization": f"Bearer {token}"}

    # Sub-step 3: list items (initial state)
    status, body = http_request(
        "GET",
        f"{backend_url}/api/items",
        headers=auth_headers,
    )
    assert status == 200, f"GET /api/items expected 200, got {status}: {body}"
    initial_items = body if isinstance(body, list) else (
        (body.get("results") or body.get("items") or []) if isinstance(body, dict) else []
    )
    print(f"  ✓ GET /api/items → 200 (initial count={len(initial_items)})")

    # Sub-step 4: create an item
    status, body = http_request(
        "POST",
        f"{backend_url}/api/items",
        body={
            "name": TEST_ITEM_NAME,
            "description": TEST_ITEM_DESCRIPTION,
            "is_completed": False,
        },
        headers=auth_headers,
    )
    assert status == 201, f"POST /api/items expected 201, got {status}: {body}"
    new_id = body.get("id") if isinstance(body, dict) else None
    assert new_id, f"create response missing id: {body}"
    assert body.get("name") == TEST_ITEM_NAME, (
        f"create response name mismatch: {body}"
    )
    assert body.get("is_completed") is False, (
        f"create response is_completed should be False: {body}"
    )
    print(
        f"  ✓ POST /api/items → 201 (id={new_id}, "
        f"name='{body.get('name')}')"
    )

    # Sub-step 5: list again — new item should appear
    status, body = http_request(
        "GET",
        f"{backend_url}/api/items",
        headers=auth_headers,
    )
    assert status == 200
    items_after = body if isinstance(body, list) else (
        (body.get("results") or body.get("items") or []) if isinstance(body, dict) else []
    )
    names = [i.get("name") for i in items_after if isinstance(i, dict)]
    assert TEST_ITEM_NAME in names, f"new item not in list after create: {names}"
    assert len(items_after) == len(initial_items) + 1, (
        f"expected list to grow by 1: before={len(initial_items)} "
        f"after={len(items_after)}"
    )
    print(
        f"  ✓ GET /api/items → 200 (count={len(items_after)}, "
        f"new item visible)"
    )

    # Sub-step 6: retrieve the item by id
    status, body = http_request(
        "GET",
        f"{backend_url}/api/items/{new_id}",
        headers=auth_headers,
    )
    assert status == 200, (
        f"GET /api/items/{new_id} expected 200, got {status}: {body}"
    )
    assert body.get("id") == new_id
    assert body.get("name") == TEST_ITEM_NAME
    print(f"  ✓ GET /api/items/{new_id} → 200 (round-trip OK)")

    # Sub-step 7: complete via the @action endpoint
    status, body = http_request(
        "POST",
        f"{backend_url}/api/items/{new_id}/complete",
        headers=auth_headers,
    )
    assert status in (200, 201), (
        f"POST /api/items/{new_id}/complete expected 200/201, "
        f"got {status}: {body}"
    )
    assert body.get("is_completed") is True, (
        f"complete response should set is_completed=True: {body}"
    )
    print(
        f"  ✓ POST /api/items/{new_id}/complete → {status} "
        f"(is_completed=True)"
    )

    # Sub-step 7a: probe whether this backend ships /api/categories
    # A real categories endpoint returns 200 with a JSON array. Some
    # backends without categories may return 200 from a catch-all
    # route, so we also check that the body is actually a list.
    probe_status, probe_body = http_request(
        "GET",
        f"{backend_url}/api/categories",
        headers=auth_headers,
    )
    has_categories = probe_status == 200 and isinstance(probe_body, list)

    if has_categories:
        # Sub-step 7b: exercise the categories API
        cat_id = exercise_categories_api(backend_url, auth_headers)

        # Sub-step 7c: create an item WITH a category_id
        print()
        print("Exercising items + categories FK...")
        status, body = http_request(
            "POST",
            f"{backend_url}/api/items",
            body={
                "name": "item-with-category",
                "description": "Item linked to a category",
                "is_completed": False,
                "category_id": cat_id,
            },
            headers=auth_headers,
        )
        assert status == 201, (
            f"POST /api/items (with category) expected 201, got {status}: {body}"
        )
        cat_item_id = body.get("id")
        assert body.get("category_id") == cat_id, (
            f"item should have category_id={cat_id}: {body}"
        )
        print(
            f"  ✓ POST /api/items → 201 (id={cat_item_id}, "
            f"category_id={cat_id})"
        )

        # Sub-step 7d: retrieve the categorized item and verify FK
        status, body = http_request(
            "GET",
            f"{backend_url}/api/items/{cat_item_id}",
            headers=auth_headers,
        )
        assert status == 200
        assert body.get("category_id") == cat_id, (
            f"retrieved item should have category_id={cat_id}: {body}"
        )
        print(
            f"  ✓ GET /api/items/{cat_item_id} → 200 "
            f"(category_id={cat_id} round-trip OK)"
        )

        # Sub-step 7e: delete the category, verify item's category_id becomes null
        status, _body = http_request(
            "DELETE",
            f"{backend_url}/api/categories/{cat_id}",
            headers=auth_headers,
        )
        assert status in (200, 204), (
            f"DELETE /api/categories/{cat_id} expected 200/204, got {status}"
        )
        print(f"  ✓ DELETE /api/categories/{cat_id} → {status}")

        status, body = http_request(
            "GET",
            f"{backend_url}/api/items/{cat_item_id}",
            headers=auth_headers,
        )
        assert status == 200
        assert body.get("category_id") is None, (
            f"after category delete, item category_id should be null: {body}"
        )
        print(
            f"  ✓ GET /api/items/{cat_item_id} → 200 "
            f"(category_id=None after category delete — SET_NULL works)"
        )
    else:
        print()
        print(
            "  · skipping categories exercise "
            "(backend does not ship /api/categories yet)"
        )

    # Sub-step S: state API — save, load, delete roundtrip.
    # Exercises the /api/state endpoints that the persistent UI filter
    # (React: useAppState, Flutter: readAppState) uses under the hood.
    print()
    print("Exercising the state API flow...")

    state_key = "integration.testFlag"
    state_value = '{"flag":true,"ts":12345}'

    # S1: save a state slice
    status, body = http_request(
        "PUT",
        f"{backend_url}/api/state/{state_key}",
        body={"value": state_value},
        headers=auth_headers,
    )
    assert status == 200, (
        f"PUT /api/state/{state_key} expected 200, got {status}: {body}"
    )
    print(f"  ✓ PUT /api/state/{state_key} → 200 (saved)")

    # S2: load all state — the saved key must be present
    status, body = http_request(
        "GET",
        f"{backend_url}/api/state",
        headers=auth_headers,
    )
    assert status == 200, (
        f"GET /api/state expected 200, got {status}: {body}"
    )
    assert isinstance(body, dict), f"state response should be dict: {body}"
    assert state_key in body, (
        f"saved key {state_key!r} not in state response: {body}"
    )
    print(
        f"  ✓ GET /api/state → 200 (contains {state_key!r})"
    )

    # S3: delete the state slice
    status, _body = http_request(
        "DELETE",
        f"{backend_url}/api/state/{state_key}",
        headers=auth_headers,
    )
    assert status in (200, 204), (
        f"DELETE /api/state/{state_key} expected 200/204, got {status}"
    )
    print(f"  ✓ DELETE /api/state/{state_key} → {status}")

    # S4: verify the slice is gone
    status, body = http_request(
        "GET",
        f"{backend_url}/api/state",
        headers=auth_headers,
    )
    assert status == 200
    assert state_key not in body, (
        f"deleted key {state_key!r} still in state response: {body}"
    )
    print(
        f"  ✓ GET /api/state → 200 ({state_key!r} removed after delete)"
    )

    # S5: anonymous state access must be rejected
    status, _body = http_request("GET", f"{backend_url}/api/state")
    assert status in (401, 403), (
        f"anonymous GET /api/state expected 401/403, got {status}"
    )
    print(
        f"  ✓ GET /api/state without token → {status} "
        f"(JWT enforcement works)"
    )

    # Sub-step 8: anonymous request must be rejected
    status, _body = http_request("GET", f"{backend_url}/api/items")
    assert status in (401, 403), (
        f"anonymous GET /api/items expected 401/403, got {status}"
    )
    print(
        f"  ✓ GET /api/items without token → {status} (JWT enforcement works)"
    )

    # Sub-step 9: invalid token must be rejected
    status, _body = http_request(
        "GET",
        f"{backend_url}/api/items",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert status in (401, 403), (
        f"invalid-token GET /api/items expected 401/403, got {status}"
    )
    print(
        f"  ✓ GET /api/items with invalid token → {status} "
        f"(JWT validation works)"
    )


# --------------------------------------------------------------------------- #
#  Top-level driver shared by every per-backend test script
# --------------------------------------------------------------------------- #


def run_frontend_backend_integration(
    *,
    frontend: Frontend,
    project_name: str,
    title: str,
    spec: BackendSpec,
    repo_root: Path,
    port: int,
    server_startup_timeout: int,
    keep: bool,
    no_skip: bool,
    expected_bundle_strings: Optional[Dict[str, str]] = None,
) -> int:
    """Run a full ``<frontend>`` + ``<backend>`` integration test.

    Returns the exit code (0 = pass, 1 = fail, 2 = setup skip).

    The orchestration mirrors the **out-of-the-box** workflow a real
    user follows: nothing is patched after gen. The driver only
    exports a ``SKEL_BACKEND_URL`` env var BEFORE invoking the gen
    scripts; ``_skels/_common/common-wrapper.sh`` writes that value
    into ``<wrapper>/.env`` while it scaffolds the wrapper, and every
    downstream artifact (React vite bundle, Flutter ``.env`` asset,
    Python backend env loader) reads the right URL from the start.

    Steps:

    1. Toolchain probe (skipped via ``EXIT_SETUP`` when missing).
    2. Pre-export ``SKEL_BACKEND_URL`` so the wrapper scaffolder bakes
       the test port into ``<wrapper>/.env`` at gen time.
    3. Generate ``backend`` and ``frontend.skel`` into the wrapper.
       (Both call ``common-wrapper.sh``, which honours
       ``SKEL_BACKEND_URL``.)
    4. Call ``frontend.build(...)`` to produce the bundle. The build
       reads the gen-time ``.env`` so the URL is correct on the first
       build — no rebuilds needed.
    5. Call ``frontend.inspect_bundle(...)`` to assert the bundle
       contains the expected strings.
    6. Run ``spec.pre_server_setup`` (Django migrations, ...).
    7. Start the backend in the background and wait for it.
    8. Exercise the canonical 9-step items API flow via Python.
    9. Run the frontend smoke (real client code → live backend).
    10. Stop the server and clean up the wrapper (unless ``keep``).
    """

    wrapper = repo_root / "_test_projects" / project_name

    print()
    print(f"=== {title} ===")
    print(f"  frontend: {frontend.name} ({frontend.skel})")
    print(f"  backend:  {spec.skeleton}")
    print(f"  wrapper:  {wrapper}")
    print(f"  port:     {port}")
    print()

    if not frontend.toolchain_probe():
        msg = (
            f"{frontend.toolchain_label} not installed "
            f"(required for the {frontend.name} build)"
        )
        if no_skip:
            print(f"  ✗ {msg}")
            return EXIT_FAIL
        print(f"  · skipping ({msg})")
        return EXIT_SETUP

    backend_url = f"http://127.0.0.1:{port}"
    final_exit = EXIT_OK
    server_proc: Optional[subprocess.Popen] = None
    log_fp = None
    server_log: Optional[Path] = None

    # Pre-export SKEL_BACKEND_URL so common-wrapper.sh propagates it
    # into <wrapper>/.env at gen time. We restore the previous value
    # in the finally block so concurrent test runs (or interactive
    # debugging in the same shell) don't inherit a stale URL.
    previous_skel_backend_url = os.environ.get("SKEL_BACKEND_URL")
    os.environ["SKEL_BACKEND_URL"] = backend_url

    try:
        # 1. Clean wrapper
        if wrapper.exists():
            print(f"  cleaning previous {wrapper}")
            shutil.rmtree(wrapper)
        wrapper.parent.mkdir(parents=True, exist_ok=True)

        # 2. Generate backend + frontend. common-wrapper.sh inside each
        #    gen invocation honours SKEL_BACKEND_URL and writes it into
        #    <wrapper>/.env, so by the time the loop exits the wrapper
        #    is already wired with the test port — zero post-gen
        #    patching needed.
        print()
        print(f"Generating services (SKEL_BACKEND_URL={backend_url})...")
        backend_slug = generate_one_service(
            repo_root=repo_root,
            wrapper_dir=wrapper,
            skeleton=spec.skeleton,
            service_label=spec.service_name,
        )
        print(f"  + {backend_slug}/  ({spec.skeleton})")

        frontend_slug = generate_one_service(
            repo_root=repo_root,
            wrapper_dir=wrapper,
            skeleton=frontend.skel,
            service_label=frontend.service_name,
        )
        print(f"  + {frontend_slug}/  ({frontend.skel})")

        # 3. Sanity check that common-wrapper.sh actually wrote the
        #    URL we asked for. If this fires, common-wrapper.sh has
        #    regressed and out-of-the-box wiring is broken.
        env_text = (wrapper / ".env").read_text(encoding="utf-8")
        assert f"BACKEND_URL={backend_url}" in env_text, (
            f"common-wrapper.sh did not propagate SKEL_BACKEND_URL "
            f"into {wrapper / '.env'} — look for the SKEL_BACKEND_URL "
            f"hook in _skels/_common/common-wrapper.sh"
        )

        # 4. Build the frontend. The build reads the gen-time .env
        #    which already has the right BACKEND_URL — no rebuilds.
        print()
        print(f"Building the {frontend.name} frontend (gen-time .env wiring)...")
        frontend_dir = wrapper / frontend_slug
        frontend.build(wrapper, frontend_dir, backend_url)

        # 5. Verify the build artifacts bake in the right values
        print()
        print(f"Inspecting the {frontend.name} build artifacts...")
        frontend.inspect_bundle(
            frontend_dir, backend_url, expected_bundle_strings
        )

        # 6. Backend-specific pre-server setup
        backend_dir = wrapper / backend_slug
        if spec.pre_server_setup:
            print()
            print("Running backend pre-server setup...")
            run_backend_setup(
                backend_dir=backend_dir,
                spec=spec,
                host="127.0.0.1",
                port=port,
            )

        # 7. Start the backend server in the background
        print()
        print(f"Starting {spec.skeleton} server on 127.0.0.1:{port}...")
        server_log = backend_dir / "test-server.log"
        log_fp = open(server_log, "wb")
        server_env = os.environ.copy()
        server_env["BACKEND_URL"] = backend_url
        server_env.update(spec.extra_env)
        server_argv = _format_argv(spec.server_argv_template, "127.0.0.1", port)
        server_proc = subprocess.Popen(
            server_argv,
            cwd=backend_dir,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            env=server_env,
        )

        if not wait_for_server(
            f"{backend_url}/api/items", timeout_s=server_startup_timeout
        ):
            print("  ✗ server did not become ready in time")
            print()
            print("  ----- server log (last 4000 chars) -----")
            try:
                print(server_log.read_text(encoding="utf-8")[-4000:])
            except OSError:
                pass
            return EXIT_FAIL
        print("  ✓ server is up")

        # 8. Run the canonical 9-step HTTP exercise via Python (cheap
        #    pre-flight that catches backend regressions immediately).
        exercise_items_api(backend_url)

        # 9. Run the FRONTEND smoke — the same 9-step flow but
        #    executed by the frontend's own client code (vitest +
        #    src/api/items.ts for React, flutter test +
        #    lib/api/items_client.dart for Flutter). This is the only
        #    step that proves the *frontend* side of the contract is
        #    correct end-to-end.
        if frontend.frontend_smoke is not None:
            print()
            print(f"Running {frontend.name} frontend smoke (real client code)...")
            frontend.frontend_smoke(frontend_dir, backend_url)
        else:
            print()
            print(f"  · {frontend.name} has no frontend_smoke configured")

        # 10. Run E2E browser tests (Playwright for React, none for
        #     Flutter yet). These drive the real built app in a
        #     headless browser, exercising form binding, DOM structure,
        #     localStorage persistence, and the wrapper-shared /api/state
        #     contract as a real user would experience it.
        if frontend.e2e is not None:
            print()
            print(f"Running {frontend.name} E2E tests (browser → vite preview → live backend)...")
            frontend.e2e(frontend_dir, backend_url, port)
        else:
            print()
            print(f"  · {frontend.name} has no E2E step configured")

        print()
        print("=== ALL CHECKS PASSED ===")

    except AssertionError as exc:
        print()
        print(f"  ✗ assertion failed: {exc}")
        if server_log and server_log.is_file():
            print()
            print("  ----- server log (last 4000 chars) -----")
            try:
                print(server_log.read_text(encoding="utf-8")[-4000:])
            except OSError:
                pass
        final_exit = EXIT_FAIL
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print()
        print(f"  ✗ subprocess error: {exc}")
        final_exit = EXIT_FAIL
    except RuntimeError as exc:
        print()
        print(f"  ✗ {exc}")
        final_exit = EXIT_FAIL
    except Exception as exc:  # noqa: BLE001 — surface anything we missed
        print()
        print(f"  ✗ unexpected error: {exc!r}")
        final_exit = EXIT_FAIL
    finally:
        # Stop the server cleanly. SIGTERM, then SIGKILL on timeout.
        if server_proc is not None and server_proc.poll() is None:
            print()
            print(f"Stopping server (pid {server_proc.pid})...")
            try:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("  (SIGTERM timed out, sending SIGKILL)")
                    server_proc.kill()
                    try:
                        server_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
            except OSError:
                pass

        if log_fp is not None:
            try:
                log_fp.close()
            except OSError:
                pass

        if keep:
            print()
            print(f"  (kept on disk: {wrapper})")
        elif final_exit != EXIT_OK:
            print()
            print(f"  (kept on disk for inspection: {wrapper})")
        else:
            print()
            print(f"Cleaning up {wrapper}...")
            shutil.rmtree(wrapper, ignore_errors=True)

        # Restore SKEL_BACKEND_URL so a subsequent call (e.g. inside
        # the same Python process from `make test-cross-stack`) does
        # not inherit the previous test's port.
        if previous_skel_backend_url is None:
            os.environ.pop("SKEL_BACKEND_URL", None)
        else:
            os.environ["SKEL_BACKEND_URL"] = previous_skel_backend_url

    return final_exit


# --------------------------------------------------------------------------- #
#  Backwards-compatible React-only entrypoint
# --------------------------------------------------------------------------- #
#
# `run_react_backend_integration` is the historical entrypoint used by
# `_bin/skel-test-react-fastapi` and (after the consolidation
# refactor) `_bin/skel-test-react-django-bolt`. It is now a thin
# shim around :func:`run_frontend_backend_integration` so existing
# scripts keep working without import changes.


def run_react_backend_integration(
    *,
    project_name: str,
    title: str,
    spec: BackendSpec,
    repo_root: Path,
    port: int,
    server_startup_timeout: int,
    keep: bool,
    no_skip: bool,
    expected_bundle_strings: Optional[Dict[str, str]] = None,
) -> int:
    """Run a full React + ``<backend>`` integration test against ``spec``.

    Forwards to :func:`run_frontend_backend_integration` with
    :data:`REACT_FRONTEND` so the older per-backend scripts keep their
    historical signature. New tests should call
    :func:`run_frontend_backend_integration` directly with an explicit
    ``frontend=`` argument.
    """

    return run_frontend_backend_integration(
        frontend=REACT_FRONTEND,
        project_name=project_name,
        title=title,
        spec=spec,
        repo_root=repo_root,
        port=port,
        server_startup_timeout=server_startup_timeout,
        keep=keep,
        no_skip=no_skip,
        expected_bundle_strings=expected_bundle_strings,
    )
