"""Shared helpers for the <frontend> + <backend> cross-stack integration tests.

`_bin/test-react-django-bolt-integration`,
`_bin/test-react-fastapi-integration`,
`_bin/test-flutter-django-bolt-integration`, and
`_bin/test-flutter-fastapi-integration` all do the same thing:

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
    """Run every entry in ``spec.pre_server_setup`` from ``backend_dir``."""

    for label, argv_template in spec.pre_server_setup:
        argv = _format_argv(argv_template, host, port)
        result = subprocess.run(
            argv,
            cwd=backend_dir,
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

    Before invoking the build we re-copy the wrapper-level ``.env`` into
    the project directory so the bundled asset reflects the freshly
    rewritten ``BACKEND_URL``. The skeleton's gen script copies the env
    on initial generation, but at that point the wrapper still has the
    default ``BACKEND_URL=http://localhost:8000`` — we need to refresh
    it AFTER the test driver rewrites the wrapper env.
    """

    wrapper_env = wrapper / ".env"
    project_env = frontend_dir / ".env"
    if wrapper_env.is_file():
        shutil.copyfile(wrapper_env, project_env)
        print(f"  ✓ refreshed {project_env.name} from <wrapper>/.env")

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


REACT_FRONTEND = Frontend(
    name="React",
    skel=FRONTEND_SKEL,
    service_name=FRONTEND_SERVICE_NAME,
    toolchain_label="Node.js / npm",
    toolchain_probe=have_node,
    build=_react_build,
    inspect_bundle=_react_inspect_bundle,
)

FLUTTER_FRONTEND = Frontend(
    name="Flutter",
    skel="flutter-skel",
    service_name="Mobile UI",
    toolchain_label="Flutter SDK",
    toolchain_probe=have_flutter,
    build=_flutter_build,
    inspect_bundle=_flutter_inspect_bundle,
)


# --------------------------------------------------------------------------- #
#  9-step HTTP exercise
# --------------------------------------------------------------------------- #


def exercise_items_api(backend_url: str) -> None:
    """Run the canonical register → login → CRUD → reject flow.

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
        body.get("results", []) if isinstance(body, dict) else []
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
        body.get("results", []) if isinstance(body, dict) else []
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

    The orchestration is the same for every (frontend, backend) pair:

    1. Toolchain probe (skipped via ``EXIT_SETUP`` when missing).
    2. Generate ``backend`` and ``frontend.skel`` into the wrapper.
    3. Rewrite ``BACKEND_URL`` in the wrapper ``.env``.
    4. Call ``frontend.build(...)`` to (re)produce the bundle.
    5. Call ``frontend.inspect_bundle(...)`` to assert the bundle
       contains the expected strings.
    6. Run ``spec.pre_server_setup`` (Django migrations, ...).
    7. Start the backend in the background and wait for it.
    8. Exercise the canonical 9-step items API flow.
    9. Stop the server and clean up the wrapper (unless ``keep``).
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

    try:
        # 1. Clean wrapper
        if wrapper.exists():
            print(f"  cleaning previous {wrapper}")
            shutil.rmtree(wrapper)
        wrapper.parent.mkdir(parents=True, exist_ok=True)

        # 2. Generate backend + frontend
        print()
        print("Generating services...")
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

        # 3. Update BACKEND_URL in wrapper .env
        print()
        print(f"Setting BACKEND_URL={backend_url} in <wrapper>/.env")
        update_wrapper_env(wrapper / ".env", "BACKEND_URL", backend_url)
        env_text = (wrapper / ".env").read_text(encoding="utf-8")
        assert f"BACKEND_URL={backend_url}" in env_text, (
            f"BACKEND_URL update did not stick in {wrapper / '.env'}"
        )

        # 4. Re-build the frontend with the updated BACKEND_URL
        print()
        print(f"Re-building the {frontend.name} frontend with the updated BACKEND_URL...")
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

        # 8. Run the canonical 9-step HTTP exercise
        exercise_items_api(backend_url)

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

    return final_exit


# --------------------------------------------------------------------------- #
#  Backwards-compatible React-only entrypoint
# --------------------------------------------------------------------------- #
#
# `run_react_backend_integration` is the historical entrypoint used by
# `_bin/test-react-fastapi-integration` and (after the consolidation
# refactor) `_bin/test-react-django-bolt-integration`. It is now a thin
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
