"""Shared driver for the K8s cross-stack tests.

Each `_bin/skel-test-k8s-react-<backend>` script is a thin wrapper
that imports :func:`run_k8s_test` from this module and passes its
backend skeleton name. The driver:

1. Generates a wrapper containing the backend (and React-style naming
   only — the React frontend is NOT actually deployed, mirroring the
   pre-refactor scripts which already only exercised the backend).
2. Builds the backend image and pushes to DockerHub via
   :mod:`_bin.skel-k8s-push` (forces ``--platform linux/amd64``).
3. Deploys via Helm to the ``paul`` k3s cluster, with retries to
   tolerate the occasional k3s API timeout.
4. Waits for pods Ready, runs Django migrations via ``kubectl exec``
   when the backend is in the django family, fetches the NodePort,
   waits for HTTP, and exercises the canonical items + orders flow.
5. Tears down with ``skel-k8s-deploy down`` unless ``--keep``.

Exit codes mirror the pre-refactor scripts:

* 0 — every check passed
* 1 — at least one check failed
* 2 — toolchain missing or setup error
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dev_skel_lib import DevSkelConfig, detect_root, load_config  # noqa: E402

from _frontend_backend_lib import (  # noqa: E402
    EXIT_FAIL,
    EXIT_OK,
    EXIT_SETUP,
    exercise_orders_api,
    http_request,
)

# Backends that talk to the helm-managed Postgres pod.
# Rust + Go currently use embedded SQLite (no AnyPool path yet).
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

# Health probes — defaults to "/health".
_HEALTH_PATHS = {
    "python-fastapi-skel": "/api/health",
    "python-django-bolt-skel": "/api/health",
    "next-js-skel": "/api/health",
    "next-js-ddd-skel": "/api/health",
}

# Container port — most backends bind 8000; Next.js binds 3000.
_SERVICE_PORTS = {"next-js-skel": 3000, "next-js-ddd-skel": 3000}

GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def _parse_args(prog: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="K8s cross-stack test (backend on k3s)",
    )
    parser.add_argument("--keep", action="store_true",
                        help="Leave k8s resources deployed after test")
    parser.add_argument("--no-skip", action="store_true",
                        help="Treat missing toolchain as hard failure")
    return parser.parse_args()


def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, **kwargs)


def _check_toolchain(no_skip: bool) -> bool:
    for tool in ["kubectl", "helm", "docker"]:
        if not shutil.which(tool):
            msg = f"{tool} not on PATH"
            if no_skip:
                print(f"  {RED}x{NC} {msg}")
                return False
            print(f"  {YELLOW}.{NC} skipping ({msg})")
            return False

    result = subprocess.run(
        ["kubectl", "cluster-info"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        msg = "kubectl cannot reach cluster"
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


def _get_nodeport(namespace: str, service: str) -> int | None:
    result = subprocess.run(
        ["kubectl", "get", "svc", service, "-n", namespace,
         "-o", "jsonpath={.spec.ports[0].nodePort}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return int(result.stdout.strip())
    return None


def _wait_for_ready(namespace: str, timeout: int = 180) -> bool:
    result = subprocess.run(
        ["kubectl", "wait", "--for=condition=Ready", "pods", "--all",
         "-n", namespace, f"--timeout={timeout}s"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def run_k8s_test(
    backend_skel: str,
    backend_service_name: str = "Items API",
    *,
    project_name: str | None = None,
) -> int:
    args = _parse_args(prog=f"skel-test-k8s-react-{backend_skel}")

    if project_name is None:
        short = backend_skel.replace("python-", "").replace("-skel", "")
        short = short.replace("java-", "").replace("rust-", "")
        project_name = f"test-k8s-react-{short}"

    use_postgres = backend_skel in _POSTGRES_SKELS
    service_port = _SERVICE_PORTS.get(backend_skel, 8000)
    health_path = _HEALTH_PATHS.get(backend_skel, "/health")
    namespace = project_name
    k3s_host = os.environ.get("SKEL_K3S_HOST", "paul")
    registry = os.environ.get("SWARM_REGISTRY", "beret")

    cfg: DevSkelConfig = load_config()
    repo_root = detect_root(SCRIPT_DIR, cfg.skel_dir)
    wrapper = repo_root / "_test_projects" / project_name

    print()
    print(f"{GREEN}=== K8s Cross-Stack Test: {backend_skel} ==={NC}")
    print(f"  k3s host:   {k3s_host}")
    print(f"  namespace:  {namespace}")
    print(f"  registry:   {registry}")
    print(f"  database:   {'postgres' if use_postgres else 'sqlite'}")
    print(f"  port:       {service_port}")
    print()

    if not _check_toolchain(args.no_skip):
        return EXIT_SETUP

    final_exit = EXIT_OK

    try:
        # Phase 1: Generate wrapper
        print(f"\n{GREEN}Phase 1: Generating wrapper...{NC}")
        if wrapper.exists():
            shutil.rmtree(wrapper)

        result = _run(
            [sys.executable, str(repo_root / "_bin" / "skel-gen-static"),
             wrapper.name, backend_skel, backend_service_name],
            cwd=wrapper.parent,
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  {RED}x{NC} skel-gen-static failed")
            print(result.stdout[-2000:] if result.stdout else "")
            print(result.stderr[-2000:] if result.stderr else "")
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} wrapper generated")

        backend_slug = _find_backend_slug(wrapper, backend_service_name)
        if not backend_slug:
            print(f"  {RED}x{NC} backend service not found in wrapper")
            return EXIT_FAIL
        print(f"  backend: {backend_slug}")

        # Phase 2: Build + push Docker image
        print(f"\n{GREEN}Phase 2: Building and pushing Docker image...{NC}")
        result = _run(
            [str(repo_root / "_bin" / "skel-k8s-push"),
             str(wrapper), "--platform", "linux/amd64"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            print(f"  {RED}x{NC} image build/push failed")
            print(result.stdout[-2000:] if result.stdout else "")
            print(result.stderr[-2000:] if result.stderr else "")
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} image pushed to {registry}")

        # Phase 3: Generate Helm chart + deploy (with retry for k3s timeouts)
        print(f"\n{GREEN}Phase 3: Deploying to k8s...{NC}")
        deploy_cmd = [
            str(repo_root / "_bin" / "skel-k8s-deploy"), "up", str(wrapper),
            "--k3s", "--namespace", namespace,
            "--set", "images.pullPolicy=Always",
        ]
        svc_name_helm = backend_slug.replace("_", "-")
        if not use_postgres:
            deploy_cmd.extend([
                "--set", "postgres.enabled=false",
                "--set",
                f"services.{svc_name_helm}.env.DATABASE_URL=sqlite:///tmp/test.db",
            ])
        if service_port != 8000:
            deploy_cmd.extend([
                "--set", f"services.{svc_name_helm}.port={service_port}",
                "--set", f"services.{svc_name_helm}.containerPort={service_port}",
            ])
        for attempt in range(1, 4):
            result = _run(deploy_cmd,
                          capture_output=True, text=True, timeout=180)
            if result.returncode == 0:
                break
            if attempt < 3:
                print(f"  {YELLOW}!{NC} deploy attempt {attempt}/3 failed,"
                      " retrying in 10s...")
                time.sleep(10)
            else:
                print(f"  {RED}x{NC} helm deploy failed after 3 attempts")
                print(result.stdout[-2000:] if result.stdout else "")
                print(result.stderr[-2000:] if result.stderr else "")
                return EXIT_FAIL
        print(f"  {GREEN}v{NC} deployed to namespace {namespace}")

        # Wait for pods
        print("  waiting for pods to be ready...")
        if not _wait_for_ready(namespace, timeout=180):
            print(f"  {RED}x{NC} pods not ready after 180s")
            subprocess.run(["kubectl", "get", "pods", "-n", namespace])
            subprocess.run(["kubectl", "logs", "-n", namespace,
                            f"deploy/{svc_name_helm}", "--tail=20"])
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} all pods ready")

        # Run migrations for Django skeletons (they need migrate before serving)
        if "django" in backend_skel:
            print("  running migrations...")
            pod_name = subprocess.run(
                ["kubectl", "get", "pod", "-n", namespace,
                 "-l", f"app.kubernetes.io/name={svc_name_helm}",
                 "-o", "jsonpath={.items[0].metadata.name}"],
                capture_output=True, text=True,
            ).stdout.strip()
            if pod_name:
                migrate_result = subprocess.run(
                    ["kubectl", "exec", "-n", namespace, pod_name, "--",
                     "python", "manage.py", "migrate", "--noinput"],
                    capture_output=True, text=True, timeout=60,
                )
                if migrate_result.returncode == 0:
                    print(f"  {GREEN}v{NC} migrations complete")
                else:
                    print(f"  {YELLOW}!{NC} migrations failed: "
                          f"{migrate_result.stderr[-200:]}")

        # Get NodePort
        nodeport = _get_nodeport(namespace, svc_name_helm)
        if not nodeport:
            print(f"  {RED}x{NC} could not get NodePort for {svc_name_helm}")
            subprocess.run(["kubectl", "get", "svc", "-n", namespace])
            return EXIT_FAIL
        backend_url = f"http://{k3s_host}:{nodeport}"
        print(f"  {GREEN}v{NC} backend at {backend_url}")

        # Wait for server to respond
        print("  waiting for server to respond...")
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                status, _ = http_request(
                    "GET", f"{backend_url}{health_path}", timeout=5,
                )
                if status == 200:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            print(f"  {RED}x{NC} server not responding after 60s")
            return EXIT_FAIL
        print(f"  {GREEN}v{NC} server is up")

        # Phase 4: HTTP exercise (inline rather than `exercise_items_api`
        # because the helm template does NOT propagate the wrapper's
        # USER_* / SUPERUSER_* seed env vars — so a fresh k8s pod has
        # no seeded accounts and the canonical helper's
        # `check_seeded_accounts` step would 401. We register a fresh
        # test user and exercise the same items + orders flow against
        # it, matching the pre-refactor scripts' behavior.)
        print(f"\n{GREEN}Phase 4: HTTP integration exercise...{NC}")

        status, body = http_request(
            "POST", f"{backend_url}/api/auth/register",
            body={
                "username": "k8s-test-user",
                "email": "k8s@test.com",
                "password": "k8s-test-pass-12345",
                "password_confirm": "k8s-test-pass-12345",
            },
        )
        assert status in (201, 400, 409), f"register: {status} {body}"
        print(f"  {GREEN}v{NC} register OK")

        status, body = http_request(
            "POST", f"{backend_url}/api/auth/login",
            body={"username": "k8s-test-user",
                  "password": "k8s-test-pass-12345"},
        )
        assert status == 200, f"login: {status} {body}"
        token = (body.get("access") or body.get("access_token")
                 or body.get("token"))
        assert token, f"no token: {body}"
        auth = {"Authorization": f"Bearer {token}"}
        print(f"  {GREEN}v{NC} login OK")

        status, body = http_request(
            "POST", f"{backend_url}/api/items",
            body={"name": "k8s-test-item", "description": "from k8s"},
            headers=auth,
        )
        assert status in (200, 201), f"create item: {status} {body}"
        item_id = body.get("id")
        print(f"  {GREEN}v{NC} POST /api/items -> {status} (id={item_id})")

        status, body = http_request(
            "GET", f"{backend_url}/api/items", headers=auth,
        )
        assert status == 200, f"list items: {status}"
        print(f"  {GREEN}v{NC} GET /api/items -> {status} "
              f"({len(body)} items)")

        status, body = http_request(
            "POST", f"{backend_url}/api/items/{item_id}/complete",
            headers=auth,
        )
        assert status == 200, f"complete: {status}"
        print(f"  {GREEN}v{NC} POST /api/items/{item_id}/complete -> 200")

        # JWT enforcement
        status, _ = http_request("GET", f"{backend_url}/api/items")
        assert status in (401, 403), f"anon expected 401: {status}"
        print(f"  {GREEN}v{NC} GET /api/items without token -> {status}")

        # Order workflow (uses the auth token we already have)
        exercise_orders_api(backend_url, auth)

        print(f"\n  {GREEN}=== ALL K8S CHECKS PASSED ==={NC}")

    except AssertionError as exc:
        print(f"\n  {RED}x{NC} assertion failed: {exc}")
        final_exit = EXIT_FAIL
    except subprocess.TimeoutExpired as exc:
        print(f"\n  {RED}x{NC} timeout: {exc}")
        final_exit = EXIT_FAIL
    except Exception as exc:
        print(f"\n  {RED}x{NC} error: {exc!r}")
        final_exit = EXIT_FAIL
    finally:
        if not args.keep:
            print(f"\n{GREEN}Cleanup...{NC}")
            subprocess.run(
                [str(repo_root / "_bin" / "skel-k8s-deploy"), "down",
                 str(wrapper), "--namespace", namespace],
                capture_output=True, timeout=60,
            )
            if wrapper.exists():
                shutil.rmtree(wrapper)
            print(f"  {GREEN}v{NC} cleaned up")
        else:
            print(f"\n  --keep: resources left in namespace {namespace}")
            print(f"  Teardown: _bin/skel-k8s-deploy down {wrapper} "
                  f"--namespace {namespace}")

    return final_exit


__all__ = ["run_k8s_test"]
