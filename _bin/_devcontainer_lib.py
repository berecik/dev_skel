"""Shared driver for the devcontainer cross-stack tests.

Each `_bin/skel-test-devcontainer-<backend>` script is a thin wrapper
that imports :func:`run_devcontainer_test` from this module and passes
its backend skeleton name + service display name. The driver:

1. Generates a wrapper containing the backend (no frontend).
2. Rewrites the wrapper-shared `.env` to point ``DATABASE_URL`` at the
   compose-managed Postgres service when the backend is in
   ``_POSTGRES_SKELS``, or at an in-container SQLite file otherwise.
3. Boots ``docker compose up -d postgres <backend>`` from the wrapper.
4. Waits for the backend to respond on ``http://127.0.0.1:<port>``.
5. Runs Django migrations inside the container when needed.
6. Exercises the canonical items + orders HTTP flow.
7. Tears down with ``docker compose down -v`` unless ``--keep``.

Exit codes mirror the existing test scripts:

* 0 — every check passed
* 1 — at least one check failed
* 2 — toolchain missing or setup error
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _frontend_backend_lib import (  # noqa: E402
    EXIT_FAIL,
    EXIT_OK,
    EXIT_SETUP,
    exercise_items_api,
    exercise_orders_api,
    http_request,
    update_wrapper_env,
)
from dev_skel_lib import DevSkelConfig, detect_root, load_config  # noqa: E402

# Backends that talk to the compose-managed Postgres pod.
_POSTGRES_SKELS = {
    "python-fastapi-skel",
    "python-django-bolt-skel",
    "python-django-skel",
    "python-flask-skel",
    "java-spring-skel",
    "java-spring-ddd-skel",
    "next-js-skel",
    "next-js-ddd-skel",
}

# Per-skel HTTP health probes. Falls back to "/health".
_HEALTH_PATHS = {
    "python-fastapi-skel": "/api/health",
    "python-django-bolt-skel": "/api/health",
    "next-js-skel": "/api/health",
    "next-js-ddd-skel": "/api/health",
}

# Container port. Most backends bind 8000; Next.js binds 3000.
_SERVICE_PORTS = {"next-js-skel": 3000, "next-js-ddd-skel": 3000}

GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def _parse_args(prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=prog,
                                     description="Devcontainer cross-stack test")
    parser.add_argument("--keep", action="store_true",
                        help="Leave docker-compose stack running after test")
    parser.add_argument("--no-skip", action="store_true",
                        help="Treat missing toolchain as hard failure")
    return parser.parse_args()


def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, **kwargs)


def _check_toolchain(no_skip: bool) -> bool:
    if not shutil.which("docker"):
        msg = "docker not on PATH"
        if no_skip:
            print(f"  {RED}x{NC} {msg}")
            return False
        print(f"  {YELLOW}.{NC} skipping ({msg})")
        return False

    result = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        msg = "docker daemon unreachable"
        if no_skip:
            print(f"  {RED}x{NC} {msg}")
            return False
        print(f"  {YELLOW}.{NC} skipping ({msg})")
        return False
    return True


def _find_backend_slug(wrapper: Path, service_name: str) -> str | None:
    for child in sorted(wrapper.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if child.name in ("contracts", "deploy"):
            continue
        ctx = child / ".skel_context.json"
        if ctx.is_file():
            try:
                data = json.loads(ctx.read_text())
            except json.JSONDecodeError:
                data = {}
            if data.get("service_name") == service_name:
                return child.name
    # Fall back: first dir that ships a Dockerfile.
    for child in sorted(wrapper.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if (child / "Dockerfile").is_file():
            return child.name
    return None


def _wait_for_compose_health(
    project: str,
    service: str,
    *,
    timeout_s: int,
) -> bool:
    """Poll ``docker compose ps`` until ``service`` is running + healthy."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "compose", "-p", project, "ps",
             "--format", "json", service],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                try:
                    info = json.loads(line)
                except json.JSONDecodeError:
                    continue
                state = info.get("State") or info.get("Status", "")
                health = info.get("Health", "") or ""
                if state == "running" and health in ("", "healthy"):
                    return True
        time.sleep(2)
    return False


def _wait_for_backend(url: str, timeout_s: int = 120) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            status, _ = http_request("GET", url, timeout=5)
            if status < 500:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _compose_logs(project: str, *services: str, tail: int = 80) -> None:
    print(f"\n{YELLOW}--- compose logs (tail={tail}) ---{NC}")
    args = ["docker", "compose", "-p", project, "logs", f"--tail={tail}"]
    args.extend(services)
    subprocess.run(args, timeout=30)


def _patch_wrapper_env(
    wrapper: Path,
    *,
    use_postgres: bool,
    sqlite_path: str = "/tmp/devcontainer-test.db",
) -> None:
    """Point DATABASE_URL/SPRING_DATASOURCE_URL at the right backend.

    For Postgres the values target the compose service hostname
    ``postgres`` (reachable inside the docker-compose network). For
    SQLite we route every backend at an ephemeral in-container path
    so ``_shared/db.sqlite3`` (which is NOT bind-mounted into the
    service) does not need to exist.
    """
    env_path = wrapper / ".env"
    if not env_path.is_file():
        raise RuntimeError(f"wrapper .env missing at {env_path}")

    # Bind every backend on 0.0.0.0 so the host port mapping is
    # actually reachable from outside the container — the wrapper's
    # default SERVICE_HOST=127.0.0.1 is only correct for bare-metal
    # local runs.
    update_wrapper_env(env_path, "SERVICE_HOST", "0.0.0.0")

    if use_postgres:
        update_wrapper_env(env_path, "DATABASE_URL",
                           "postgresql://devskel:devskel@postgres:5432/devskel")
        update_wrapper_env(env_path, "DATABASE_JDBC_URL",
                           "jdbc:postgresql://postgres:5432/devskel")
        update_wrapper_env(env_path, "SPRING_DATASOURCE_URL",
                           "jdbc:postgresql://postgres:5432/devskel")
        update_wrapper_env(env_path, "SPRING_DATASOURCE_USERNAME", "devskel")
        update_wrapper_env(env_path, "SPRING_DATASOURCE_PASSWORD", "devskel")
        update_wrapper_env(env_path, "DATABASE_ENGINE", "postgresql")
        update_wrapper_env(env_path, "DATABASE_NAME", "devskel")
        update_wrapper_env(env_path, "DATABASE_HOST", "postgres")
        update_wrapper_env(env_path, "DATABASE_PORT", "5432")
        update_wrapper_env(env_path, "DATABASE_USER", "devskel")
        update_wrapper_env(env_path, "DATABASE_PASSWORD", "devskel")
    else:
        update_wrapper_env(env_path, "DATABASE_URL",
                           f"sqlite:///{sqlite_path}")
        update_wrapper_env(env_path, "DATABASE_JDBC_URL",
                           f"jdbc:sqlite:{sqlite_path}")


def _pin_backend_platform(wrapper: Path, service: str, platform: str) -> None:
    """Inject a ``platform: <platform>`` line into the backend service block.

    Idempotent: skips when the field is already present. Used to force
    ``linux/amd64`` for skels (django-bolt) that lack arm64 wheels.
    """
    compose_path = wrapper / "docker-compose.yml"
    if not compose_path.is_file():
        return
    text = compose_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    target_header = f"  {service}:"
    while i < len(lines):
        out.append(lines[i])
        if lines[i].rstrip() == target_header:
            # Walk forward to see if `platform:` is already set inside
            # this service block (block ends at next non-indented or
            # next 2-space-indented service header).
            j = i + 1
            already_set = False
            while j < len(lines):
                line = lines[j]
                if line.startswith("  ") and not line.startswith("    "):
                    break  # next service block
                if line.strip().startswith("platform:"):
                    already_set = True
                    break
                j += 1
            if not already_set:
                out.append(f"    platform: {platform}")
        i += 1
    compose_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _run_django_migrate_oneoff(
    project: str,
    service: str,
    cwd: Path,
) -> bool:
    """Run ``manage.py migrate`` in a one-off container.

    Using ``docker compose run --rm`` avoids racing with the long-lived
    backend container — django-bolt's ``runbolt`` server crashes on
    startup when the auth tables do not exist yet, which would leave
    the backend container in ``exited`` state by the time we tried to
    ``compose exec`` into it.
    """
    cmd = ["docker", "compose", "-p", project, "run", "--rm",
           "--no-deps", "--entrypoint", "",
           service, "python", "manage.py", "migrate", "--noinput"]
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True,
                            text=True, timeout=180)
    if result.returncode != 0:
        print(f"  {YELLOW}!{NC} migrate stderr: {result.stderr[-500:]}")
        return False
    return True


def run_devcontainer_test(
    backend_skel: str,
    service_name: str = "Items API",
    *,
    project_name: str | None = None,
) -> int:
    args = _parse_args(prog=f"skel-test-devcontainer-{backend_skel}")

    if project_name is None:
        # Mirror the k8s naming convention.
        short = backend_skel.replace("python-", "").replace("-skel", "")
        short = short.replace("java-", "").replace("rust-", "")
        project_name = f"test-devcontainer-{short}"

    use_postgres = backend_skel in _POSTGRES_SKELS
    service_port = _SERVICE_PORTS.get(backend_skel, 8000)
    health_path = _HEALTH_PATHS.get(backend_skel, "/health")

    cfg: DevSkelConfig = load_config()
    repo_root = detect_root(SCRIPT_DIR, cfg.skel_dir)
    wrapper = repo_root / "_test_projects" / project_name

    print()
    print(f"{GREEN}=== Devcontainer Test: {backend_skel} ==={NC}")
    print(f"  project:    {project_name}")
    print(f"  backend:    {backend_skel}")
    print(f"  database:   {'postgres' if use_postgres else 'sqlite'}")
    print(f"  port:       {service_port}")
    print()

    if not _check_toolchain(args.no_skip):
        return EXIT_SETUP

    final_exit: int = EXIT_OK
    backend_slug: str | None = None

    try:
        # Phase 1: Generate wrapper
        print(f"\n{GREEN}Phase 1: Generating wrapper...{NC}")
        if wrapper.exists():
            shutil.rmtree(wrapper)

        result = _run(
            [sys.executable, str(repo_root / "_bin" / "skel-gen-static"),
             wrapper.name, backend_skel, service_name],
            cwd=wrapper.parent,
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  {RED}x{NC} skel-gen-static failed")
            print(result.stdout[-1500:] if result.stdout else "")
            print(result.stderr[-1500:] if result.stderr else "")
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} wrapper generated")

        backend_slug = _find_backend_slug(wrapper, service_name)
        if not backend_slug:
            print(f"  {RED}x{NC} backend service not found in wrapper")
            return EXIT_FAIL
        print(f"  backend slug: {backend_slug}")

        # Phase 2: Patch wrapper .env for the test database
        print(f"\n{GREEN}Phase 2: Configuring wrapper .env...{NC}")
        _patch_wrapper_env(wrapper, use_postgres=use_postgres)
        print(f"  {GREEN}v{NC} .env wired for "
              f"{'postgres' if use_postgres else 'sqlite'}")

        # Pin the backend service to linux/amd64 — some skels
        # (django-bolt) only ship prebuilt wheels for amd64; on Apple
        # Silicon the default arm64 build path falls back to compiling
        # Rust from source. Postgres stays on the host's native
        # platform (the alpine arm64 image is cached locally).
        _pin_backend_platform(wrapper, backend_slug, "linux/amd64")

        # Phase 3: Build images + bring up postgres first so migrations
        # can run before the (potentially fragile) backend boot.
        print(f"\n{GREEN}Phase 3: Building images + starting postgres...{NC}")
        if use_postgres:
            up_pg_cmd = ["docker", "compose", "-p", project_name,
                         "up", "-d", "--build", "postgres"]
            result = _run(up_pg_cmd, cwd=wrapper, capture_output=True,
                          text=True, timeout=600)
            if result.returncode != 0:
                print(f"  {RED}x{NC} docker compose up postgres failed")
                print(result.stdout[-1500:] if result.stdout else "")
                print(result.stderr[-1500:] if result.stderr else "")
                return EXIT_FAIL
            print("  waiting for postgres to be healthy...")
            if not _wait_for_compose_health(project_name, "postgres",
                                            timeout_s=60):
                print(f"  {RED}x{NC} postgres never reported healthy")
                _compose_logs(project_name, "postgres")
                return EXIT_FAIL
            print(f"  {GREEN}v{NC} postgres healthy")

        # Build the backend image without starting it.
        build_cmd = ["docker", "compose", "-p", project_name,
                     "build", backend_slug]
        result = _run(build_cmd, cwd=wrapper, capture_output=True,
                      text=True, timeout=900)
        if result.returncode != 0:
            print(f"  {RED}x{NC} docker compose build failed")
            print(result.stdout[-1500:] if result.stdout else "")
            print(result.stderr[-1500:] if result.stderr else "")
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} backend image built")

        # Run Django migrations as a one-off container so the long-
        # lived backend never sees an empty database (django-bolt
        # crashes hard otherwise).
        if "django" in backend_skel and use_postgres:
            print("  running migrations (one-off)...")
            if not _run_django_migrate_oneoff(project_name, backend_slug,
                                              cwd=wrapper):
                return EXIT_FAIL
            print(f"  {GREEN}v{NC} migrations complete")

        # Phase 4: Start the backend and wait for it to respond
        backend_url = f"http://127.0.0.1:{service_port}"
        print(f"\n{GREEN}Phase 4: Starting backend + waiting for HTTP at "
              f"{backend_url}...{NC}")
        # `--no-deps` skips bringing up postgres for SQLite-only skels;
        # without it docker compose would auto-pull postgres because of
        # the wrapper's `depends_on: postgres` and conflict on port 5432
        # with any concurrently-running stack.
        up_be_cmd = ["docker", "compose", "-p", project_name, "up", "-d"]
        if not use_postgres:
            up_be_cmd.append("--no-deps")
        up_be_cmd.append(backend_slug)
        result = _run(up_be_cmd, cwd=wrapper, capture_output=True,
                      text=True, timeout=120)
        if result.returncode != 0:
            print(f"  {RED}x{NC} docker compose up backend failed")
            print(result.stdout[-1500:] if result.stdout else "")
            print(result.stderr[-1500:] if result.stderr else "")
            return EXIT_FAIL

        if not _wait_for_backend(f"{backend_url}{health_path}",
                                 timeout_s=120):
            print(f"  {RED}x{NC} backend never responded on {health_path}")
            _compose_logs(project_name, backend_slug)
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} backend responding on {health_path}")

        # Warm-up: hit a DB-touching endpoint with a long timeout so
        # skels that lazy-initialise their DB on the first request
        # (Next.js: schema init + bcrypt SALT=12 seed takes 5-8s, well
        # over the canonical 10s http_request budget) get to do that
        # work outside the seed-verification window that follows.
        print("  warming up backend (lazy-init + first-request JIT)...")
        try:
            http_request(
                "POST", f"{backend_url}/api/auth/login",
                body={"username": "user", "password": "secret"},
                timeout=60,
            )
        except Exception:
            pass  # warm-up is best-effort

        # Phase 5: HTTP exercise (items + orders)
        print(f"\n{GREEN}Phase 5: HTTP integration exercise...{NC}")
        exercise_items_api(backend_url)
        exercise_orders_api(backend_url)

        print(f"\n  {GREEN}=== ALL DEVCONTAINER CHECKS PASSED ==={NC}")

    except AssertionError as exc:
        print(f"\n  {RED}x{NC} assertion failed: {exc}")
        if backend_slug:
            _compose_logs(project_name, backend_slug)
        final_exit = EXIT_FAIL
    except subprocess.TimeoutExpired as exc:
        print(f"\n  {RED}x{NC} timeout: {exc}")
        if backend_slug:
            _compose_logs(project_name, backend_slug)
        final_exit = EXIT_FAIL
    except Exception as exc:
        print(f"\n  {RED}x{NC} error: {exc!r}")
        final_exit = EXIT_FAIL
    finally:
        if not args.keep:
            print(f"\n{GREEN}Cleanup...{NC}")
            subprocess.run(
                ["docker", "compose", "-p", project_name, "down", "-v",
                 "--remove-orphans"],
                cwd=wrapper if wrapper.exists() else None,
                capture_output=True, timeout=120,
            )
            if wrapper.exists():
                shutil.rmtree(wrapper)
            print(f"  {GREEN}v{NC} cleaned up")
        else:
            print(f"\n  --keep: stack left running (project={project_name})")
            print(f"  Teardown: cd {wrapper} && docker compose -p "
                  f"{project_name} down -v --remove-orphans")

    return final_exit


__all__ = ["run_devcontainer_test"]
