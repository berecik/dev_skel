# Phase 7 — Kubernetes & Helm Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship whole-project AI-assisted Kubernetes & Helm lifecycle on top of the Phase 5 static baseline: Tier-2 per-service add-ons, drift-safe file-level separation, always-kind E2E on the hot path, and a new fourth phase in `skel-gen-ai`.

**Architecture:** Extend `_bin/skel-deploy` with four new subcommands (`bootstrap`, `sync`, `diff`, `e2e`). Add `run_kubernetes_phase()` + `_kube_diagnose()` to `_bin/skel_ai_lib.py`. Ship a single shared AI manifest at `_skels/_common/manifests/_kubernetes.py` that dispatches on `service.tech`. Emit a `./project kube` forwarder from `common-wrapper.sh`. Wire the new phase into `skel-gen-ai` after the service test-fix loop converges.

**Tech Stack:** Python 3.11+ (existing `_bin/` tooling), Helm 3.x, `kind`, `kubeconform`, `kubectl`, `docker`, Ollama (`qwen3-coder:30b`), LangChain+FAISS via `skel_rag`.

**Reference spec:** `docs/superpowers/specs/2026-04-19-phase7-kubernetes-lifecycle-design.md`

---

## File structure

**New files:**

| Path | Responsibility |
| ---- | -------------- |
| `_skels/_common/manifests/_kubernetes.py` | Single shared AI manifest: dispatch table (tech → Tier-2 files), system prompt, per-file prompts, fix prompt. |
| `_bin/skel-test-kube-phase` | Fast no-LLM smoke runner (exits 2 when `kind`/`docker`/`helm`/`kubeconform` missing). |
| `_bin/skel-test-kube-e2e` | Opt-in real-cluster runner (`kind` up + `helm install` + health smoke). |
| `tests/test_kube_diagnose.py` | Pytest-free unit test for `_kube_diagnose` against fixture JSON. (Actually a standalone script under `_bin/skel-test-kube-diagnose` to match project convention.) |

**Modified files:**

| Path | Change |
| ---- | ------ |
| `_bin/skel-deploy` | Relocate Tier-1 output under `templates/_generated/`; add `bootstrap`, `sync`, `diff`, `e2e` subcommands; emit `_managed/` + `overrides/` scaffolding. |
| `_bin/skel_ai_lib.py` | Add `run_kubernetes_phase()`, `_kube_diagnose()`, `KubernetesResult` dataclass, manifest loader for `_kubernetes.py`. |
| `_bin/skel-gen-ai` | Call `run_kubernetes_phase()` after `run_test_and_fix_loop` converges, behind `--no-kube` opt-out. |
| `_skels/_common/common-wrapper.sh` | Emit `./project kube` forwarder (dispatches `bootstrap/sync/diff/e2e` to `skel-deploy`). |
| `_skels/_common/helm/templates/*` | Nothing structural; just relocated output path. |
| `Makefile` | Add `test-kube-phase`, `test-kube-phase-ai`, `test-kube-e2e` targets; wire into `.PHONY`. |
| `ROADMAP.md` | Mark Phase 7 as shipped at end of implementation. |
| `CHANGELOG.md` | Add `[2026-04-DD] — Phase 7` entry at end of implementation. |
| `CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`, `_docs/LLM-MAINTENANCE.md` | Document the new phase + `./project kube` workflow. |

---

## Execution order

Tasks are ordered so each lands with its own test, and earlier tasks don't block later ones. Commits after every task. Target size: each task ~15–45 min.

---

## Task 1: Tier-1 relocation — write under `templates/_generated/`

**Files:**
- Modify: `_bin/skel-deploy:123-168` (`cmd_helm_gen`)
- Modify: `_bin/skel-test-project-ux` (if assertions reference the old path — grep first)

**Rationale:** The drift-safe layout requires static chart templates to live under `templates/_generated/` so `sync` can wipe+rewrite without touching user overrides. Scaffold `_managed/` and `overrides/` as empty dirs so their intent is visible in the generated tree.

- [ ] **Step 1: Write the failing assertion**

Create `_bin/skel-test-kube-layout` (new):

```python
#!/usr/bin/env python3
"""Smoke test: skel-deploy helm-gen writes the 3-tier layout."""
from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = REPO_ROOT / "_test_projects" / "test-kube-layout"

def _run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)

def main() -> int:
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    gen = _run(["make", "gen-stack-web", f"NAME=_test_projects/{TEST_DIR.name}"], cwd=REPO_ROOT)
    if gen.returncode != 0:
        print(gen.stdout + gen.stderr, file=sys.stderr)
        return 1
    dep = _run(["_bin/skel-deploy", "helm-gen", str(TEST_DIR)], cwd=REPO_ROOT)
    if dep.returncode != 0:
        print(dep.stdout + dep.stderr, file=sys.stderr)
        return 1
    templates = TEST_DIR / "deploy" / "helm" / "templates"
    required = [
        templates / "_generated" / "service-deployment.yaml",
        templates / "_generated" / "namespace.yaml",
        templates / "_generated" / "ingress.yaml",
        templates / "_generated" / "postgres.yaml",
        templates / "_managed",
        templates / "overrides",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        print(f"[kube-layout] FAIL: missing {missing}", file=sys.stderr)
        return 1
    # Idempotent overrides preservation
    marker = templates / "overrides" / "_marker.yaml"
    marker.write_text("# user\n", encoding="utf-8")
    _run(["_bin/skel-deploy", "helm-gen", str(TEST_DIR)], cwd=REPO_ROOT)
    if not marker.exists():
        print("[kube-layout] FAIL: overrides/_marker.yaml was wiped", file=sys.stderr)
        return 1
    shutil.rmtree(TEST_DIR)
    print("[kube-layout] OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

Make executable: `chmod +x _bin/skel-test-kube-layout`.

- [ ] **Step 2: Run to confirm failure**

```bash
_bin/skel-test-kube-layout
```

Expected: `FAIL: missing [...]/_generated/service-deployment.yaml` because the current helm-gen writes flat into `templates/`.

- [ ] **Step 3: Modify `_bin/skel-deploy` `cmd_helm_gen` to write under `_generated/` + scaffold `_managed/` and `overrides/`**

Change lines 131–163 so:

```python
def cmd_helm_gen(args: argparse.Namespace) -> int:
    wrapper = Path(args.wrapper_dir).resolve()
    data = _read_project_yml(wrapper)

    project_name = data["project"].get("name", wrapper.name)
    namespace = data["kubernetes"].get("namespace", "devskel")
    repository = data["images"].get("repository", "")

    helm_dir = wrapper / "deploy" / "helm"
    generated_dir = helm_dir / "templates" / "_generated"
    managed_dir = helm_dir / "templates" / "_managed"
    overrides_dir = helm_dir / "templates" / "overrides"
    tests_dir = generated_dir / "tests"

    # Tier-1 is always wiped + rewritten
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Tier-2 + Tier-3 scaffolded once; Tier-3 never touched afterwards
    managed_dir.mkdir(parents=True, exist_ok=True)
    overrides_dir.mkdir(parents=True, exist_ok=True)
    (overrides_dir / ".gitkeep").touch()

    replacements = {
        "PROJECT_NAME": project_name,
        "KUBE_NAMESPACE": namespace,
        "IMAGE_REPOSITORY": repository,
        "SERVICES_VALUES": _generate_services_values(data["services"]),
    }

    # Chart.yaml / values*.yaml live at the chart root (Tier-1 flat files)
    for tpl in HELM_TEMPLATES.glob("*.tpl"):
        out_name = tpl.name.removesuffix(".tpl")
        (helm_dir / out_name).write_text(_render_template(tpl, replacements))
        print(f"  + deploy/helm/{out_name}")

    # Static templates go under _generated/
    src_templates = HELM_TEMPLATES / "templates"
    for src in src_templates.rglob("*"):
        if src.is_file():
            rel = src.relative_to(src_templates)
            dst = generated_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  + deploy/helm/templates/_generated/{rel}")

    (helm_dir / ".helmignore").write_text(".git\n.gitignore\n__pycache__\n*.pyc\n")
    print(f"\nHelm chart generated at: {helm_dir}")
    return 0
```

- [ ] **Step 4: Run to confirm pass**

```bash
_bin/skel-test-kube-layout
```

Expected: `[kube-layout] OK`

- [ ] **Step 5: Add the smoke to Makefile**

Insert after `test-project-ux-keep` target (line ~497):

```make
test-kube-layout: ## Smoke: helm-gen writes 3-tier layout
	@echo "$(GREEN)=== Helm 3-tier layout smoke ===$(NC)"
	@_bin/skel-test-kube-layout
```

Add `test-kube-layout` to the `.PHONY` list at line 31.

- [ ] **Step 6: Verify existing tests still pass**

```bash
make test-project-ux
```

Expected: still green. (The stack generators don't call helm-gen; this confirms we didn't regress Phase 6.)

- [ ] **Step 7: Commit**

```bash
git add _bin/skel-deploy _bin/skel-test-kube-layout Makefile
git commit -m "Relocate Tier-1 Helm output to templates/_generated/; scaffold _managed/ + overrides/ for Phase 7 layout. Add \`make test-kube-layout\` smoke."
```

---

## Task 2: Add `_kube_diagnose` helper with fixtures

**Files:**
- Modify: `_bin/skel_ai_lib.py` (append new function near other helpers)
- Create: `_bin/skel-test-kube-diagnose`
- Create: `_bin/_fixtures/kube_diagnose/pods.json`
- Create: `_bin/_fixtures/kube_diagnose/events.json`
- Create: `_bin/_fixtures/kube_diagnose/expected_bundle.txt`

**Rationale:** Isolating the parser from real `kubectl` makes it fast to iterate on bundle format. Real invocation is layered on top in Task 5.

- [ ] **Step 1: Create fixtures** (realistic `kubectl` JSON output captured once, stored verbatim)

`_bin/_fixtures/kube_diagnose/pods.json`:

```json
{
  "items": [
    {
      "metadata": {"name": "items-api-abc123", "namespace": "devskel"},
      "status": {
        "phase": "Running",
        "containerStatuses": [{
          "name": "api",
          "restartCount": 4,
          "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "back-off"}}
        }]
      }
    },
    {
      "metadata": {"name": "items-api-ok-zzz", "namespace": "devskel"},
      "status": {
        "phase": "Running",
        "containerStatuses": [{"name": "api", "restartCount": 0, "ready": true, "state": {"running": {}}}]
      }
    }
  ]
}
```

`_bin/_fixtures/kube_diagnose/events.json`:

```json
{
  "items": [
    {"type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container", "involvedObject": {"name": "items-api-abc123"}, "lastTimestamp": "2026-04-19T10:00:00Z"}
  ]
}
```

`_bin/_fixtures/kube_diagnose/expected_bundle.txt`:

```
FAILING_RESOURCES:
  - pod/items-api-abc123  status=CrashLoopBackOff   restarts=4

EVENTS (last 20):
  Warning BackOff: Back-off restarting failed container (items-api-abc123)
```

- [ ] **Step 2: Write failing test**

Create `_bin/skel-test-kube-diagnose`:

```python
#!/usr/bin/env python3
"""Smoke test for _kube_diagnose()."""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from skel_ai_lib import _kube_diagnose_from_json  # noqa: E402

FIXTURES = HERE / "_fixtures" / "kube_diagnose"

def main() -> int:
    pods = json.loads((FIXTURES / "pods.json").read_text())
    events = json.loads((FIXTURES / "events.json").read_text())
    expected = (FIXTURES / "expected_bundle.txt").read_text().strip()
    got = _kube_diagnose_from_json(pods=pods, events=events, describes={}, logs={}).strip()
    if got != expected:
        print("[kube-diagnose] FAIL — diff:", file=sys.stderr)
        print("EXPECTED:\n" + expected, file=sys.stderr)
        print("GOT:\n" + got, file=sys.stderr)
        return 1
    print("[kube-diagnose] OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`chmod +x _bin/skel-test-kube-diagnose`.

- [ ] **Step 3: Run to confirm ImportError**

```bash
_bin/skel-test-kube-diagnose
```

Expected: `ImportError: cannot import name '_kube_diagnose_from_json'`.

- [ ] **Step 4: Add `_kube_diagnose_from_json` + `_kube_diagnose` to `skel_ai_lib.py`**

Near the end of `_bin/skel_ai_lib.py`, before the `__all__` list:

```python
def _kube_diagnose_from_json(
    *,
    pods: dict,
    events: dict,
    describes: dict[str, str],
    logs: dict[str, str],
) -> str:
    """Render a deterministic diagnostic bundle from parsed kubectl JSON."""
    lines: list[str] = []
    lines.append("FAILING_RESOURCES:")
    failing = []
    for item in pods.get("items", []):
        name = item["metadata"]["name"]
        for cs in item.get("status", {}).get("containerStatuses", []):
            waiting = cs.get("state", {}).get("waiting") or {}
            reason = waiting.get("reason")
            restarts = cs.get("restartCount", 0)
            if reason:
                failing.append((name, reason, restarts))
                lines.append(
                    f"  - pod/{name}  status={reason}   restarts={restarts}"
                )
    if not failing:
        lines.append("  (none)")

    lines.append("")
    lines.append("EVENTS (last 20):")
    for ev in (events.get("items") or [])[-20:]:
        typ = ev.get("type", "Normal")
        reason = ev.get("reason", "")
        msg = ev.get("message", "")
        obj = (ev.get("involvedObject") or {}).get("name", "")
        lines.append(f"  {typ} {reason}: {msg} ({obj})")

    if describes:
        lines.append("")
        lines.append("DESCRIBE (truncated to 40 lines each):")
        for name, text in describes.items():
            lines.append(f"  === {name} ===")
            for ln in text.splitlines()[:40]:
                lines.append(f"  {ln}")

    if logs:
        lines.append("")
        lines.append("LOGS (last 50 lines per failing container):")
        for name, text in logs.items():
            lines.append(f"  === {name} ===")
            for ln in text.splitlines()[-50:]:
                lines.append(f"  {ln}")

    return "\n".join(lines) + "\n"


def _kube_diagnose(wrapper_dir: Path, namespace: str) -> str:
    """Collect kubectl state for the failing resources; feed into _kube_diagnose_from_json."""
    import json as _json
    import subprocess as _sp

    def _kj(args: list[str]) -> dict:
        r = _sp.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            return {}
        try:
            return _json.loads(r.stdout)
        except _json.JSONDecodeError:
            return {}

    pods = _kj(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])
    events = _kj(["kubectl", "get", "events", "-n", namespace, "-o", "json"])

    describes: dict[str, str] = {}
    logs: dict[str, str] = {}
    for item in pods.get("items", []):
        name = item["metadata"]["name"]
        for cs in item.get("status", {}).get("containerStatuses", []):
            if cs.get("state", {}).get("waiting"):
                d = _sp.run(
                    ["kubectl", "describe", "pod", name, "-n", namespace],
                    capture_output=True, text=True,
                )
                describes[f"pod/{name}"] = d.stdout
                lg = _sp.run(
                    ["kubectl", "logs", name, "-c", cs["name"], "-n", namespace, "--tail=50"],
                    capture_output=True, text=True,
                )
                logs[f"{name}/{cs['name']}"] = lg.stdout
                break
    return _kube_diagnose_from_json(pods=pods, events=events, describes=describes, logs=logs)
```

Add both names to the `__all__` list at the bottom of the file (search for existing `__all__` and append).

- [ ] **Step 5: Run to confirm pass**

```bash
_bin/skel-test-kube-diagnose
```

Expected: `[kube-diagnose] OK`

- [ ] **Step 6: Commit**

```bash
git add _bin/skel_ai_lib.py _bin/skel-test-kube-diagnose _bin/_fixtures/kube_diagnose/
git commit -m "Add _kube_diagnose bundle renderer in skel_ai_lib. Deterministic parser tested against fixture kubectl JSON; separates parsing from real cluster calls."
```

---

## Task 3: Add `_skels/_common/manifests/_kubernetes.py` manifest

**Files:**
- Create: `_skels/_common/manifests/_kubernetes.py`

**Rationale:** Static manifest with dispatch + prompts. No runtime logic here — consumed by `run_kubernetes_phase` in Task 5.

- [ ] **Step 1: Write the file**

Create `_skels/_common/manifests/_kubernetes.py`:

```python
"""Shared Kubernetes Tier-2 AI manifest for Phase 7.

Dispatches on ``service.tech`` (from ``dev_skel.project.yml``) to
decide which Tier-2 files each service gets under
``deploy/helm/templates/_managed/<svc>/``.

The manifest is loaded by ``skel_ai_lib.run_kubernetes_phase``. It
intentionally ships no Python logic — consumers walk the dicts.
"""

from __future__ import annotations

DISPATCH: dict[str, list[str]] = {
    "python-django":      ["migration-job.yaml", "configmap.yaml", "hpa.yaml"],
    "python-django-bolt": ["migration-job.yaml", "configmap.yaml", "hpa.yaml"],
    "python-fastapi":     ["configmap.yaml", "hpa.yaml"],
    "python-flask":       ["configmap.yaml", "hpa.yaml"],
    "java-spring":        ["configmap.yaml", "hpa.yaml", "jvm-env.yaml"],
    "rust-actix":         ["configmap.yaml", "hpa.yaml"],
    "rust-axum":          ["configmap.yaml", "hpa.yaml"],
    "next-js":            ["configmap.yaml", "hpa.yaml"],
    "ts-react":           ["nginx-configmap.yaml"],
    "flutter":            [],
}

SYSTEM_PROMPT = """You are generating Kubernetes YAML for ONE service in a
multi-service Helm chart.

RULES (non-negotiable):
1. Output a valid Helm template. Use `{{ .Release.Name }}`,
   `{{ .Values.services.<svc>.* }}` where appropriate.
2. Write ONLY to `deploy/helm/templates/_managed/<svc>/<filename>`.
   Do not touch `_generated/` (Tier-1) or `overrides/` (user).
3. Never include cluster-scoped resources (Namespace,
   ClusterRole, ClusterRoleBinding, CRDs) — those are Tier-1.
4. Every resource MUST carry `metadata.labels.app.kubernetes.io/name`,
   `app.kubernetes.io/instance`, and `app.kubernetes.io/managed-by: Helm`.
5. Use `apiVersion` + `kind` that passes `kubeconform` on k8s 1.28+.
6. Output raw YAML only. No markdown fences.
"""

FILE_PROMPTS: dict[str, str] = {
    "migration-job.yaml": """Generate a Helm Job that runs the service's
database migrations before the Deployment is ready. Use a Helm hook
annotation `helm.sh/hook: pre-install,pre-upgrade`, `helm.sh/hook-weight: "-5"`,
`helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded`. The Job runs
the same image as the service; command depends on tech:
- `python-django` / `python-django-bolt`: `python manage.py migrate --noinput`.
The Job must mount the same JWT + DATABASE_URL env vars as the Deployment
(reference them via envFrom from the service ConfigMap once it exists).
""",
    "configmap.yaml": """Generate a Helm ConfigMap named
`{{ .Release.Name }}-<svc>-config` holding the service's non-secret env
vars derived from `dev_skel.project.yml` + the wrapper `.env.example`
(everything BUT `JWT_SECRET` and `DATABASE_URL` which come from the
Tier-1 Secret and Postgres service respectively). Include at minimum
`LOG_FORMAT`, `OTEL_SERVICE_NAME`, and the service's own `SERVICE_URL_<SLUG>`.
""",
    "hpa.yaml": """Generate a HorizontalPodAutoscaler v2 for the service.
minReplicas=1, maxReplicas=5, targetCPU=70%, targetMemory=80%. ScaleTargetRef
points at the Deployment `{{ .Release.Name }}-<svc>`.
""",
    "jvm-env.yaml": """Generate a Helm ConfigMap named
`{{ .Release.Name }}-<svc>-jvm` with JVM tuning envs:
`JAVA_OPTS="-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC -XX:+HeapDumpOnOutOfMemoryError"`.
Mount into the Deployment via envFrom (the Deployment is generated Tier-1,
so reference by configmap name only — do not emit a Deployment).
""",
    "nginx-configmap.yaml": """Generate a Helm ConfigMap named
`{{ .Release.Name }}-<svc>-nginx` with an `nginx.conf` key. Serve the SPA
from `/usr/share/nginx/html`, fallback to `/index.html` for client-side
routing, proxy `/api/*` to `http://{{ .Release.Name }}-<backend>:<port>`
where `<backend>` and `<port>` are passed via template values.
""",
}

FIX_PROMPT = """The previous Kubernetes generation for {service_id} failed
the cluster smoke. Here is the diagnostic bundle:

{diagnostic_bundle}

Rewrite ONLY the files under
`deploy/helm/templates/_managed/{service_id}/` to fix the failure.
Do not touch `_generated/` or `overrides/`. Output the full new content
of each file you are changing, preceded by `===FILE: <relative-path>===`
on its own line.
"""
```

- [ ] **Step 2: Write validation script**

Create `_bin/skel-test-kube-manifest`:

```python
#!/usr/bin/env python3
"""Verify _kubernetes.py manifest shape."""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "_skels" / "_common" / "manifests"))
from _kubernetes import DISPATCH, FILE_PROMPTS, FIX_PROMPT, SYSTEM_PROMPT  # noqa: E402

def main() -> int:
    required_techs = {
        "python-django", "python-django-bolt", "python-fastapi",
        "python-flask", "java-spring", "rust-actix", "rust-axum",
        "next-js", "ts-react", "flutter",
    }
    missing = required_techs - DISPATCH.keys()
    if missing:
        print(f"[kube-manifest] FAIL: missing tech keys: {missing}", file=sys.stderr)
        return 1

    referenced = {f for files in DISPATCH.values() for f in files}
    undefined = referenced - FILE_PROMPTS.keys()
    if undefined:
        print(
            f"[kube-manifest] FAIL: DISPATCH references files with no prompt: {undefined}",
            file=sys.stderr,
        )
        return 1

    if "{service_id}" not in FIX_PROMPT or "{diagnostic_bundle}" not in FIX_PROMPT:
        print("[kube-manifest] FAIL: FIX_PROMPT missing required placeholders", file=sys.stderr)
        return 1

    if not SYSTEM_PROMPT.strip():
        print("[kube-manifest] FAIL: SYSTEM_PROMPT empty", file=sys.stderr)
        return 1

    print("[kube-manifest] OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`chmod +x _bin/skel-test-kube-manifest`.

- [ ] **Step 3: Run — expect pass**

```bash
_bin/skel-test-kube-manifest
```

Expected: `[kube-manifest] OK`

- [ ] **Step 4: Commit**

```bash
git add _skels/_common/manifests/_kubernetes.py _bin/skel-test-kube-manifest
git commit -m "Add _skels/_common/manifests/_kubernetes.py: shared AI dispatch table + per-file prompts for Phase 7 Tier-2 generation. Validation smoke verifies all 10 techs covered and every dispatched filename has a prompt."
```

---

## Task 4: Add `run_kubernetes_phase()` skeleton (no cluster, static-only)

**Files:**
- Modify: `_bin/skel_ai_lib.py` — append `KubernetesResult` + `run_kubernetes_phase()`
- Modify: `_bin/skel_ai_lib.py` — extend `__all__`

**Rationale:** Get the orchestration shape + return contract right before adding the AI + cluster logic. This task delivers a phase that: calls `skel-deploy helm-gen`, scaffolds empty `_managed/<svc>/` dirs, runs `helm lint`, returns structured success/failure. Subsequent tasks fill in the AI generation and kind E2E.

- [ ] **Step 1: Write failing test**

Create `_bin/skel-test-kube-phase`:

```python
#!/usr/bin/env python3
"""Smoke: run_kubernetes_phase() in static-only mode (--no-kube, no-ai)."""
from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "_bin"))
from skel_ai_lib import run_kubernetes_phase  # noqa: E402

TEST_DIR = REPO_ROOT / "_test_projects" / "test-kube-phase"

def _run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, **kw)

def _skip_if(missing_bin: str) -> bool:
    r = _run(["which", missing_bin])
    if r.returncode != 0:
        print(f"[kube-phase] SKIP — {missing_bin} not installed", file=sys.stderr)
        return True
    return False

def main() -> int:
    if _skip_if("helm"):
        return 2

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    gen = _run(["make", "gen-stack-web", f"NAME=_test_projects/{TEST_DIR.name}"], cwd=REPO_ROOT)
    if gen.returncode != 0:
        print(gen.stdout + gen.stderr, file=sys.stderr)
        return 1

    result = run_kubernetes_phase(
        client=None,
        wrapper_dir=TEST_DIR,
        project_yml=None,  # read from disk
        skip_ai=True,
        skip_kind=True,
    )

    if not result.ok:
        print(f"[kube-phase] FAIL: {result.error}", file=sys.stderr)
        return 1

    templates = TEST_DIR / "deploy" / "helm" / "templates"
    if not (templates / "_generated" / "service-deployment.yaml").exists():
        print("[kube-phase] FAIL: _generated not populated", file=sys.stderr)
        return 1
    for svc in ("items_api", "web_ui"):
        if not (templates / "_managed" / svc).is_dir():
            print(f"[kube-phase] FAIL: _managed/{svc}/ not created", file=sys.stderr)
            return 1

    shutil.rmtree(TEST_DIR)
    print("[kube-phase] OK (static-only)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`chmod +x _bin/skel-test-kube-phase`.

- [ ] **Step 2: Run to confirm ImportError**

```bash
_bin/skel-test-kube-phase
```

Expected: `ImportError: cannot import name 'run_kubernetes_phase'`.

- [ ] **Step 3: Implement skeleton**

In `_bin/skel_ai_lib.py`, near the existing `run_integration_phase`:

```python
@dataclass
class KubernetesResult:
    ok: bool
    error: Optional[str] = None
    helm_lint_output: str = ""
    generated_files: list[Path] = field(default_factory=list)
    failed_resources: list[str] = field(default_factory=list)
    fix_iterations: int = 0


def run_kubernetes_phase(
    client,
    wrapper_dir: Path,
    project_yml,
    *,
    fix_timeout_m: int = 30,
    keep_kind: bool = False,
    skip_kind: bool = False,
    skip_ai: bool = False,
) -> "KubernetesResult":
    """Phase 4: Tier-1 helm-gen + Tier-2 AI add-ons + kind E2E + fix loop.

    ``skip_ai=True`` runs only Tier-1 and scaffolds empty ``_managed/<svc>/``
    directories. ``skip_kind=True`` skips the cluster E2E.
    """
    import subprocess as _sp
    from pathlib import Path as _P

    wrapper_dir = _P(wrapper_dir).resolve()
    repo_root = _P(__file__).resolve().parent.parent

    # Tier-1: invoke skel-deploy helm-gen as a subprocess
    helm_gen = _sp.run(
        [str(repo_root / "_bin" / "skel-deploy"), "helm-gen", str(wrapper_dir)],
        capture_output=True, text=True,
    )
    if helm_gen.returncode != 0:
        return KubernetesResult(ok=False, error=f"helm-gen failed: {helm_gen.stderr}")

    # Load project yml to enumerate services
    if project_yml is None:
        import yaml
        project_yml = yaml.safe_load(
            (wrapper_dir / "dev_skel.project.yml").read_text()
        )

    managed_root = wrapper_dir / "deploy" / "helm" / "templates" / "_managed"
    for svc in project_yml.get("services", []):
        svc_id = svc["id"]
        (managed_root / svc_id).mkdir(parents=True, exist_ok=True)

    generated_files: list[_P] = []

    if not skip_ai:
        # Tier-2 generation happens in Task 5. Until then this is a no-op.
        pass

    # helm lint (always)
    lint = _sp.run(
        ["helm", "lint", str(wrapper_dir / "deploy" / "helm")],
        capture_output=True, text=True,
    )
    if lint.returncode != 0:
        return KubernetesResult(
            ok=False,
            error=f"helm lint failed",
            helm_lint_output=lint.stdout + lint.stderr,
        )

    if not skip_kind:
        # kind E2E comes in Task 6.
        pass

    return KubernetesResult(
        ok=True,
        helm_lint_output=lint.stdout,
        generated_files=generated_files,
    )
```

Add `KubernetesResult` and `run_kubernetes_phase` to `__all__`.

- [ ] **Step 4: Run — expect pass**

```bash
_bin/skel-test-kube-phase
```

Expected: `[kube-phase] OK (static-only)`

- [ ] **Step 5: Wire into Makefile**

Add to `Makefile` after `test-kube-layout`:

```make
test-kube-phase: ## Smoke: run_kubernetes_phase() static path
	@echo "$(GREEN)=== Kubernetes phase (static-only) smoke ===$(NC)"
	@_bin/skel-test-kube-phase
```

Add to `.PHONY`.

- [ ] **Step 6: Commit**

```bash
git add _bin/skel_ai_lib.py _bin/skel-test-kube-phase Makefile
git commit -m "Add run_kubernetes_phase() skeleton in skel_ai_lib: Tier-1 helm-gen + _managed/<svc>/ scaffolding + helm lint. AI (skip_ai) + kind (skip_kind) still opt-out; later tasks fill them in."
```

---

## Task 5: Add Tier-2 AI generation to `run_kubernetes_phase`

**Files:**
- Modify: `_bin/skel_ai_lib.py` — replace the `if not skip_ai: pass` block with real dispatch
- Add: `_ask_ollama_for_kubernetes` helper

**Rationale:** Wire the `_kubernetes.py` manifest into the phase. Uses the existing Ollama client; no RAG retrieval needed (prompts are small and generic).

- [ ] **Step 1: Extend the phase smoke to exercise AI (optional-gated)**

Modify `_bin/skel-test-kube-phase` to add a second invocation with `skip_ai=False` ONLY when `OLLAMA_URL` reaches. Reuse the existing skip/exit-2 pattern.

```python
# After the static-only check, if Ollama is up, do a real-AI pass
import os, urllib.request
def _ollama_up() -> bool:
    try:
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/tags"
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

if _ollama_up():
    print("[kube-phase] Ollama reachable — running AI pass")
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    _run(["make", "gen-stack-web", f"NAME=_test_projects/{TEST_DIR.name}"], cwd=REPO_ROOT)
    result = run_kubernetes_phase(
        client=None, wrapper_dir=TEST_DIR, project_yml=None,
        skip_kind=True, skip_ai=False,
    )
    if not result.ok:
        print(f"[kube-phase] FAIL (AI): {result.error}", file=sys.stderr)
        return 1
    for svc in ("items_api",):  # only backends get configmap.yaml
        cfg = TEST_DIR / "deploy" / "helm" / "templates" / "_managed" / svc / "configmap.yaml"
        if not cfg.exists():
            print(f"[kube-phase] FAIL: _managed/{svc}/configmap.yaml not written", file=sys.stderr)
            return 1
    print("[kube-phase] AI pass OK")
```

- [ ] **Step 2: Run to confirm AI-branch failure**

```bash
_bin/skel-test-kube-phase
```

Expected: static branch passes; AI branch fails with `_managed/items_api/configmap.yaml not written` (because `skip_ai=False` is currently a no-op).

- [ ] **Step 3: Implement `_ask_ollama_for_kubernetes` + wire into `run_kubernetes_phase`**

Add to `skel_ai_lib.py` above `run_kubernetes_phase`:

```python
def _ask_ollama_for_kubernetes(
    client: "OllamaClient",
    *,
    service_id: str,
    service_tech: str,
    service_ctx: dict,
    filename: str,
    system_prompt: str,
    file_prompt: str,
) -> str:
    """Return raw YAML text for one Tier-2 file."""
    user = (
        f"SERVICE_ID: {service_id}\n"
        f"SERVICE_TECH: {service_tech}\n"
        f"SERVICE_CTX: {service_ctx}\n\n"
        f"TASK: Generate `{filename}` for this service.\n\n"
        f"{file_prompt}"
    )
    raw = client.complete(system=system_prompt, user=user)
    return clean_response(raw, language="yaml")
```

Replace the `if not skip_ai: pass` block in `run_kubernetes_phase` with:

```python
if not skip_ai:
    # Load Tier-2 manifest
    import importlib.util
    manifest_path = repo_root / "_skels" / "_common" / "manifests" / "_kubernetes.py"
    spec = importlib.util.spec_from_file_location("_kubernetes", manifest_path)
    kube_manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kube_manifest)

    # A client may not have been passed explicitly (tests/dry-run); construct default
    if client is None:
        client = OllamaClient(OllamaConfig.from_env())

    for svc in project_yml.get("services", []):
        svc_id = svc["id"]
        tech = svc.get("tech", "")
        files = kube_manifest.DISPATCH.get(tech, [])
        if not files:
            continue
        svc_dir = managed_root / svc_id
        svc_dir.mkdir(parents=True, exist_ok=True)
        for fname in files:
            prompt = kube_manifest.FILE_PROMPTS[fname]
            yaml_text = _ask_ollama_for_kubernetes(
                client,
                service_id=svc_id,
                service_tech=tech,
                service_ctx=svc,
                filename=fname,
                system_prompt=kube_manifest.SYSTEM_PROMPT,
                file_prompt=prompt,
            )
            # Path-traversal guard
            dst = (svc_dir / fname).resolve()
            if not str(dst).startswith(str(svc_dir.resolve())):
                return KubernetesResult(
                    ok=False,
                    error=f"AI wrote outside _managed/{svc_id}/ — rejecting",
                )
            dst.write_text(yaml_text)
            generated_files.append(dst)
```

- [ ] **Step 4: Run — expect AI pass green**

```bash
_bin/skel-test-kube-phase
```

Expected (if Ollama is running): `[kube-phase] AI pass OK`.
Expected (if Ollama down): static branch OK, AI branch skipped by the `_ollama_up()` guard.

- [ ] **Step 5: Commit**

```bash
git add _bin/skel_ai_lib.py _bin/skel-test-kube-phase
git commit -m "Wire _kubernetes.py Tier-2 AI generation into run_kubernetes_phase. Dispatches on service.tech, writes only under _managed/<svc>/, rejects path-traversal attempts. Smoke runs AI branch when Ollama is up, skips cleanly otherwise."
```

---

## Task 6: Add `kind` E2E to `run_kubernetes_phase`

**Files:**
- Modify: `_bin/skel_ai_lib.py` — replace `if not skip_kind: pass`
- Create: `_bin/skel-test-kube-e2e`

**Rationale:** With kind, lifetime is the most error-prone part. Encapsulate `create → install → health smoke → delete` with a context manager so cleanup always runs.

- [ ] **Step 1: Write the E2E smoke (opt-in)**

Create `_bin/skel-test-kube-e2e`:

```python
#!/usr/bin/env python3
"""Opt-in E2E: real kind cluster + helm install + /api/health smoke."""
from __future__ import annotations
import os, shutil, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "_bin"))
from skel_ai_lib import run_kubernetes_phase  # noqa: E402

TEST_DIR = REPO_ROOT / "_test_projects" / "test-kube-e2e"

def _which(name: str) -> bool:
    return subprocess.run(["which", name], capture_output=True).returncode == 0

def main() -> int:
    for tool in ("kind", "helm", "kubectl", "docker"):
        if not _which(tool):
            print(f"[kube-e2e] SKIP — {tool} not installed", file=sys.stderr)
            return 2

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    gen = subprocess.run(
        ["make", "gen-stack-web", f"NAME=_test_projects/{TEST_DIR.name}"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if gen.returncode != 0:
        print(gen.stdout + gen.stderr, file=sys.stderr)
        return 1

    result = run_kubernetes_phase(
        client=None,
        wrapper_dir=TEST_DIR,
        project_yml=None,
        skip_kind=False,
        skip_ai=(os.environ.get("KUBE_E2E_SKIP_AI", "1") == "1"),
        keep_kind=False,
    )
    if not result.ok:
        print(f"[kube-e2e] FAIL: {result.error}", file=sys.stderr)
        return 1

    print("[kube-e2e] OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`chmod +x _bin/skel-test-kube-e2e`.

- [ ] **Step 2: Run to confirm `skip_kind=False` fails today**

```bash
KUBE_E2E_SKIP_AI=1 _bin/skel-test-kube-e2e
```

Expected: fails — kind branch is still a no-op, so we never actually verify pod readiness and the eventual install will fail because no real cluster exists. Exit 1.

- [ ] **Step 3: Implement the kind lifecycle**

Add to `skel_ai_lib.py` near other kube helpers:

```python
import contextlib as _contextlib

@_contextlib.contextmanager
def _kind_cluster(name: str, *, keep: bool):
    """Context manager: create kind cluster, yield, always delete unless keep."""
    import subprocess as _sp
    create = _sp.run(
        ["kind", "create", "cluster", "--name", name, "--wait", "120s"],
        capture_output=True, text=True,
    )
    if create.returncode != 0:
        raise RuntimeError(f"kind create failed: {create.stderr}")
    try:
        yield name
    finally:
        if not keep:
            _sp.run(["kind", "delete", "cluster", "--name", name],
                    capture_output=True, text=True)


def _helm_install_and_wait(
    wrapper_dir: Path,
    release: str,
    namespace: str,
    *,
    timeout: str = "180s",
) -> tuple[int, str]:
    """Run helm install --wait; return (rc, combined output)."""
    import subprocess as _sp
    chart = wrapper_dir / "deploy" / "helm"
    _sp.run(["kubectl", "create", "namespace", namespace],
            capture_output=True, text=True)
    r = _sp.run(
        ["helm", "upgrade", "--install", release, str(chart),
         "-n", namespace, "--wait", f"--timeout={timeout}",
         "-f", str(chart / "values-local.yaml")],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def _smoke_health(project_yml: dict, namespace: str) -> list[str]:
    """Return a list of failing health-check identifiers (empty = all green)."""
    import subprocess as _sp
    failures: list[str] = []
    for svc in project_yml.get("services", []):
        if svc.get("kind") != "backend":
            continue
        svc_id_k8s = svc["id"].replace("_", "-")
        port = svc.get("port", 8000)
        # kubectl port-forward in background, curl, then kill
        pf = _sp.Popen(
            ["kubectl", "port-forward", f"svc/{svc_id_k8s}",
             f"18080:{port}", "-n", namespace],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
        try:
            import time, urllib.request
            time.sleep(2)
            try:
                with urllib.request.urlopen("http://127.0.0.1:18080/api/health", timeout=5) as r:
                    if r.status != 200:
                        failures.append(f"{svc_id_k8s}: status {r.status}")
            except Exception as exc:
                failures.append(f"{svc_id_k8s}: {exc}")
        finally:
            pf.terminate()
            pf.wait(timeout=5)
    return failures
```

Replace `if not skip_kind: pass` with:

```python
if not skip_kind:
    import yaml as _yaml  # already imported earlier; keep local for clarity
    namespace = project_yml.get("kubernetes", {}).get("namespace", "devskel")
    release = project_yml.get("project", {}).get("name", wrapper_dir.name)
    cluster_name = f"devskel-{release}"[:40]
    try:
        with _kind_cluster(cluster_name, keep=keep_kind):
            rc, out = _helm_install_and_wait(wrapper_dir, release, namespace)
            if rc != 0:
                return KubernetesResult(
                    ok=False, error=f"helm install failed: {out[-500:]}",
                )
            failed = _smoke_health(project_yml, namespace)
            if failed:
                bundle = _kube_diagnose(wrapper_dir, namespace)
                return KubernetesResult(
                    ok=False,
                    error="health smoke failed",
                    failed_resources=failed,
                    helm_lint_output=bundle,
                )
    except RuntimeError as exc:
        return KubernetesResult(ok=False, error=str(exc))
```

- [ ] **Step 4: Re-run — expect green on a system with kind**

```bash
KUBE_E2E_SKIP_AI=1 _bin/skel-test-kube-e2e
```

Expected (with kind installed + reachable Docker): `[kube-e2e] OK` (takes ~3–5 min).
Expected (without kind): `[kube-e2e] SKIP — kind not installed` (exit 2).

- [ ] **Step 5: Wire into Makefile**

Add after `test-kube-phase`:

```make
test-kube-e2e: ## Opt-in: real kind cluster + helm install + health smoke
	@echo "$(GREEN)=== Kubernetes E2E (real kind cluster) ===$(NC)"
	@_bin/skel-test-kube-e2e
```

Add to `.PHONY`.

- [ ] **Step 6: Commit**

```bash
git add _bin/skel_ai_lib.py _bin/skel-test-kube-e2e Makefile
git commit -m "Add kind-cluster E2E to run_kubernetes_phase: _kind_cluster context manager, _helm_install_and_wait, _smoke_health. Always-delete cluster on exit unless keep_kind=True. make test-kube-e2e opt-in smoke; skips cleanly when kind/docker/kubectl/helm missing."
```

---

## Task 7: Add the K8s fix-loop

**Files:**
- Modify: `_bin/skel_ai_lib.py` — wrap the kind E2E in a fix-loop

**Rationale:** When pods fail, the AI gets the diagnostic bundle and rewrites `_managed/<svc>/<file>` files. Bounded by `fix_timeout_m` and max iterations.

- [ ] **Step 1: Add iteration budget, fix prompt dispatch**

In `run_kubernetes_phase`, replace the `if not skip_kind:` block with a fix-loop:

```python
if not skip_kind:
    import time as _time
    namespace = project_yml.get("kubernetes", {}).get("namespace", "devskel")
    release = project_yml.get("project", {}).get("name", wrapper_dir.name)
    cluster_name = f"devskel-{release}"[:40]
    started = _time.monotonic()
    deadline = started + fix_timeout_m * 60
    fix_iterations = 0
    last_error = ""
    try:
        with _kind_cluster(cluster_name, keep=keep_kind):
            while True:
                rc, out = _helm_install_and_wait(wrapper_dir, release, namespace)
                failed: list[str] = []
                if rc != 0:
                    last_error = f"helm install failed: {out[-500:]}"
                else:
                    failed = _smoke_health(project_yml, namespace)
                    if not failed:
                        break  # success
                    last_error = f"failed: {failed}"

                if _time.monotonic() >= deadline or skip_ai:
                    bundle = _kube_diagnose(wrapper_dir, namespace)
                    return KubernetesResult(
                        ok=False,
                        error=last_error,
                        failed_resources=failed,
                        helm_lint_output=bundle,
                        fix_iterations=fix_iterations,
                    )

                # Ask AI to fix
                bundle = _kube_diagnose(wrapper_dir, namespace)
                applied = _ask_ollama_to_fix_kubernetes(
                    client=client,
                    wrapper_dir=wrapper_dir,
                    project_yml=project_yml,
                    diagnostic_bundle=bundle,
                )
                fix_iterations += 1
                if not applied:
                    return KubernetesResult(
                        ok=False,
                        error=f"fix iteration {fix_iterations} produced no edits",
                        failed_resources=failed,
                        helm_lint_output=bundle,
                        fix_iterations=fix_iterations,
                    )
                # Loop around: helm install (upgrade path) picks up changes
    except RuntimeError as exc:
        return KubernetesResult(ok=False, error=str(exc), fix_iterations=fix_iterations)

    return KubernetesResult(
        ok=True, helm_lint_output=lint.stdout,
        generated_files=generated_files, fix_iterations=fix_iterations,
    )
```

Note: the pre-existing `return KubernetesResult(ok=True, ...)` at the end of the function must be moved into each branch (the skip-kind branch still needs its own success return). Refactor accordingly.

- [ ] **Step 2: Implement `_ask_ollama_to_fix_kubernetes`**

Below `_ask_ollama_for_kubernetes`:

```python
def _ask_ollama_to_fix_kubernetes(
    *,
    client: "OllamaClient",
    wrapper_dir: Path,
    project_yml: dict,
    diagnostic_bundle: str,
) -> bool:
    """Apply one round of AI-driven fixes to _managed/ files.

    Returns True if any file was rewritten, False otherwise.
    """
    import importlib.util
    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = repo_root / "_skels" / "_common" / "manifests" / "_kubernetes.py"
    spec = importlib.util.spec_from_file_location("_kubernetes", manifest_path)
    kube_manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kube_manifest)

    managed_root = wrapper_dir / "deploy" / "helm" / "templates" / "_managed"
    any_written = False

    for svc in project_yml.get("services", []):
        svc_id = svc["id"]
        svc_dir = managed_root / svc_id
        if not svc_dir.is_dir():
            continue
        user = kube_manifest.FIX_PROMPT.format(
            service_id=svc_id,
            diagnostic_bundle=diagnostic_bundle,
        )
        current_files = {
            f.name: f.read_text() for f in svc_dir.glob("*.yaml")
        }
        user += f"\n\nCURRENT FILES:\n"
        for name, txt in current_files.items():
            user += f"\n===FILE: {name}===\n{txt}\n"

        raw = client.complete(system=kube_manifest.SYSTEM_PROMPT, user=user)
        # Parse ===FILE: <path>=== blocks
        import re
        blocks = re.split(r"^===FILE:\s*(.+?)\s*===\s*$", raw, flags=re.MULTILINE)
        # blocks = [prefix, name1, body1, name2, body2, ...]
        for i in range(1, len(blocks), 2):
            rel = blocks[i].strip()
            body = blocks[i + 1] if i + 1 < len(blocks) else ""
            dst = (svc_dir / rel).resolve()
            if not str(dst).startswith(str(svc_dir.resolve())):
                continue  # path traversal attempt
            dst.write_text(clean_response(body, language="yaml"))
            any_written = True

    return any_written
```

- [ ] **Step 3: Unit test against a forced-failure scenario (fixture-based)**

Add to `_bin/skel-test-kube-diagnose` a second test that feeds a failing pods.json with a specific error message and asserts the fix-prompt builder (parseable by splitting `===FILE:===` markers) produces a non-empty list. Stub `client.complete` to return:

```
===FILE: configmap.yaml===
apiVersion: v1
kind: ConfigMap
...
```

And assert `_ask_ollama_to_fix_kubernetes` wrote the file.

Skip details here — follow the existing unit-test pattern from Task 2.

- [ ] **Step 4: Run**

```bash
_bin/skel-test-kube-diagnose
_bin/skel-test-kube-phase
```

Both should pass.

- [ ] **Step 5: Commit**

```bash
git add _bin/skel_ai_lib.py _bin/skel-test-kube-diagnose
git commit -m "Add Phase 7 fix-loop: on kind-cluster health failure, feed _kube_diagnose bundle + current _managed/ files into _ask_ollama_to_fix_kubernetes, parse ===FILE: blocks, write back with path-traversal guard, re-run helm upgrade until green or fix_timeout_m exceeded."
```

---

## Task 8: Add `skel-deploy bootstrap` / `sync` / `diff` / `e2e` subcommands

**Files:**
- Modify: `_bin/skel-deploy` — register 4 new subcommands

**Rationale:** Thin CLI wrappers around `run_kubernetes_phase` + helpers. No new logic; orchestration only.

- [ ] **Step 1: Add `bootstrap` subcommand**

In `main()` of `skel-deploy`, after the existing `status` subparser:

```python
p = sub.add_parser("bootstrap", help="Full Tier-1 + Tier-2 + kind E2E lifecycle")
p.add_argument("wrapper_dir", help="Path to wrapper")
p.add_argument("--no-kube", action="store_true", help="Skip kind E2E")
p.add_argument("--keep-kube", action="store_true", help="Don't delete kind after")
p.add_argument("--fix-timeout", type=int, default=30, help="Fix loop budget (min)")
p.set_defaults(func=cmd_bootstrap)

p = sub.add_parser("sync", help="Regenerate managed trees; preserve overrides/")
p.add_argument("wrapper_dir")
p.add_argument("--yes", action="store_true")
p.add_argument("--e2e", action="store_true")
p.set_defaults(func=cmd_sync)

p = sub.add_parser("diff", help="Preview sync diff")
p.add_argument("wrapper_dir")
p.add_argument("--rendered", action="store_true",
               help="Compare helm-templated YAML rather than raw files")
p.set_defaults(func=cmd_diff)

p = sub.add_parser("e2e", help="Standalone kind install + health smoke")
p.add_argument("wrapper_dir")
p.add_argument("--keep-kube", action="store_true")
p.set_defaults(func=cmd_e2e)
```

- [ ] **Step 2: Implement each command**

```python
def cmd_bootstrap(args) -> int:
    sys.path.insert(0, str(SCRIPT_DIR))
    from skel_ai_lib import run_kubernetes_phase
    result = run_kubernetes_phase(
        client=None,
        wrapper_dir=Path(args.wrapper_dir),
        project_yml=None,
        fix_timeout_m=args.fix_timeout,
        skip_kind=args.no_kube,
        keep_kind=args.keep_kube,
        skip_ai=False,
    )
    print(f"ok={result.ok} fix_iterations={result.fix_iterations}")
    if not result.ok:
        print(result.error, file=sys.stderr)
        return 1
    return 0


def cmd_sync(args) -> int:
    import tempfile, shutil, difflib
    wrapper = Path(args.wrapper_dir).resolve()
    # Generate fresh tree to a temp dir then compare
    with tempfile.TemporaryDirectory() as td:
        staging = Path(td) / "deploy" / "helm"
        staging.parent.mkdir(parents=True)
        # shallow-copy chart values, regenerate templates into staging
        # ... simplified: just rerun helm-gen on a clone
        shutil.copytree(wrapper, staging.parent.parent, dirs_exist_ok=True)
        args2 = argparse.Namespace(wrapper_dir=str(staging.parent.parent))
        cmd_helm_gen(args2)
        # Compute file tree diff
        current = wrapper / "deploy" / "helm" / "templates"
        new = staging / "templates"
        changed = _tree_diff(current, new, ignore_subdir="overrides")
        if not changed and not args.yes:
            print("No changes.")
            return 0
        if not args.yes:
            print("The following managed files will change:")
            for p in changed:
                print(f"  {p}")
            resp = input("Apply? [y/N] ")
            if resp.lower() != "y":
                return 1
        # Wipe + copy managed trees
        shutil.rmtree(current / "_generated", ignore_errors=True)
        shutil.rmtree(current / "_managed", ignore_errors=True)
        shutil.copytree(new / "_generated", current / "_generated")
        shutil.copytree(new / "_managed", current / "_managed")
        # Validate
        lint = subprocess.run(
            ["helm", "lint", str(wrapper / "deploy" / "helm")],
            capture_output=True, text=True,
        )
        if lint.returncode != 0:
            print(lint.stdout + lint.stderr, file=sys.stderr)
            return 1
        if args.e2e:
            return cmd_e2e(argparse.Namespace(
                wrapper_dir=str(wrapper), keep_kube=False,
            ))
        return 0


def cmd_diff(args) -> int:
    import tempfile, shutil
    wrapper = Path(args.wrapper_dir).resolve()
    with tempfile.TemporaryDirectory() as td:
        staging = Path(td)
        shutil.copytree(wrapper, staging, dirs_exist_ok=True)
        cmd_helm_gen(argparse.Namespace(wrapper_dir=str(staging)))
        current = wrapper / "deploy" / "helm" / "templates"
        new = staging / "deploy" / "helm" / "templates"
        if args.rendered:
            rc1 = subprocess.run(
                ["helm", "template", str(wrapper / "deploy" / "helm")],
                capture_output=True, text=True,
            )
            rc2 = subprocess.run(
                ["helm", "template", str(staging / "deploy" / "helm")],
                capture_output=True, text=True,
            )
            import difflib as _dl
            for line in _dl.unified_diff(
                rc1.stdout.splitlines(keepends=True),
                rc2.stdout.splitlines(keepends=True),
                fromfile="current", tofile="new",
            ):
                sys.stdout.write(line)
        else:
            for p in _tree_diff(current, new, ignore_subdir="overrides"):
                print(p)
    return 0


def cmd_e2e(args) -> int:
    sys.path.insert(0, str(SCRIPT_DIR))
    from skel_ai_lib import run_kubernetes_phase
    result = run_kubernetes_phase(
        client=None,
        wrapper_dir=Path(args.wrapper_dir),
        project_yml=None,
        skip_kind=False,
        skip_ai=True,  # only validate, don't regenerate
        keep_kind=args.keep_kube,
    )
    return 0 if result.ok else 1


def _tree_diff(a: Path, b: Path, *, ignore_subdir: str) -> list[str]:
    changed: list[str] = []
    for base in (a, b):
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(base)
            if rel.parts and rel.parts[0] == ignore_subdir:
                continue
            other = (b if base == a else a) / rel
            if not other.exists() or other.read_bytes() != p.read_bytes():
                if str(rel) not in changed:
                    changed.append(str(rel))
    return sorted(changed)
```

- [ ] **Step 3: Smoke manually**

```bash
_bin/skel-deploy bootstrap --no-kube _test_projects/test-kube-phase
# Make a trivial edit to a _generated/ file, then:
_bin/skel-deploy diff _test_projects/test-kube-phase
# Should list the edited file.
_bin/skel-deploy sync --yes _test_projects/test-kube-phase
# Should wipe + rewrite it.
```

- [ ] **Step 4: Commit**

```bash
git add _bin/skel-deploy
git commit -m "Add skel-deploy bootstrap/sync/diff/e2e subcommands. bootstrap runs the full Phase-4 lifecycle. sync regenerates managed trees with a confirmation prompt (--yes skips) and preserves overrides/. diff shows a file-tree diff (--rendered compares helm template output). e2e runs the kind smoke standalone."
```

---

## Task 9: Emit `./project kube` forwarder in `common-wrapper.sh`

**Files:**
- Modify: `_skels/_common/common-wrapper.sh` — extend the `cat >"$MAIN_DIR/project"` heredoc

**Rationale:** Users run `./project kube <cmd>` inside the wrapper; the forwarder finds `dev_skel` root and shells out to `skel-deploy`.

- [ ] **Step 1: Locate the `./project` heredoc in common-wrapper.sh**

It's at line ~1007. Inside the `case "$cmd"` switch (around line 1152), add a new `kube)` branch:

```bash
case "$cmd" in
  test|lint|build)
    shift
    _run_aggregated "$cmd"
    ;;
  graph)
    ...
    ;;
  kube)
    shift
    if [[ -z "${DEV_SKEL_ROOT:-}" ]]; then
      for candidate in \
        "$SCRIPT_DIR/.dev_skel_root" \
        "$HOME/dev_skel" \
        "$HOME/src/dev_skel" \
        "/opt/dev_skel" \
        "/usr/local/share/dev_skel"; do
        if [[ -f "$candidate/_bin/skel-deploy" ]]; then
          DEV_SKEL_ROOT="$candidate"
          break
        fi
      done
    fi
    if [[ -z "${DEV_SKEL_ROOT:-}" ]] || [[ ! -x "$DEV_SKEL_ROOT/_bin/skel-deploy" ]]; then
      echo "[project kube] ERROR: cannot find dev_skel checkout." >&2
      echo "[project kube] Set DEV_SKEL_ROOT=<path> or install dev_skel to one of the default locations." >&2
      exit 1
    fi
    exec python3 "$DEV_SKEL_ROOT/_bin/skel-deploy" "$@" "$SCRIPT_DIR"
    ;;
  ...
esac
```

Also extend the `--help` block:

```
  kube <cmd>         Bootstrap/sync/diff/e2e the project's Helm chart
                     (forwards to skel-deploy with wrapper_dir=.)
```

- [ ] **Step 2: Verify emission by regenerating a stack**

```bash
rm -rf _test_projects/test-project-kube && make gen-stack-web NAME=_test_projects/test-project-kube
grep -c "^  kube)" _test_projects/test-project-kube/project
# Expected: 1
_test_projects/test-project-kube/project --help | grep -i kube
# Expected: shows the kube help line
```

- [ ] **Step 3: Commit**

```bash
git add _skels/_common/common-wrapper.sh
git commit -m "Add ./project kube <cmd> forwarder in common-wrapper.sh. Auto-detects DEV_SKEL_ROOT with the same walk-up logic as ./ai and ./backport, exits actionably when the checkout is missing. Forwards bootstrap/sync/diff/e2e to _bin/skel-deploy with wrapper_dir=\\$SCRIPT_DIR."
```

---

## Task 10: Wire Phase 4 into `skel-gen-ai`

**Files:**
- Modify: `_bin/skel-gen-ai` — add `--no-kube` CLI flag + call `run_kubernetes_phase` after `run_test_and_fix_loop`

**Rationale:** Gen-time hot path. After the service test-fix loop converges green, run the K8s phase. On failure, non-zero exit but service code stays put.

- [ ] **Step 1: Add `--no-kube` + `--keep-kube` + `--kube-fix-timeout` CLI flags**

Find the `argparse` setup in `skel-gen-ai` and add:

```python
p.add_argument("--no-kube", action="store_true",
               help="Skip the Phase-4 Kubernetes lifecycle.")
p.add_argument("--keep-kube", action="store_true",
               help="Leave the kind cluster running after Phase 4 (debug).")
p.add_argument("--kube-fix-timeout", type=int, default=30,
               help="Kubernetes fix-loop budget in minutes (default 30).")
```

- [ ] **Step 2: Call `run_kubernetes_phase` at the right control-flow point**

Find the two spots where `run_integration_phase` is followed by the test-fix loop (lines 737 and 1210 in the current file). After the test-fix loop returns green AND `not args.no_kube`:

```python
if not getattr(args, "no_kube", False):
    from skel_ai_lib import run_kubernetes_phase
    kube_res = run_kubernetes_phase(
        client=client,
        wrapper_dir=wrapper_dir,
        project_yml=None,
        fix_timeout_m=getattr(args, "kube_fix_timeout", 30),
        keep_kind=getattr(args, "keep_kube", False),
    )
    if not kube_res.ok:
        print(f"[skel-gen-ai] Kubernetes phase FAILED: {kube_res.error}",
              file=sys.stderr)
        print(f"[skel-gen-ai] Service code is still on disk. Re-run with "
              f"`./project kube sync --e2e` to retry.", file=sys.stderr)
        return 1
    print(f"[skel-gen-ai] Kubernetes phase OK "
          f"(fix_iterations={kube_res.fix_iterations})")
```

Apply the same block in the `skel-add` path (the second invocation near line 1210).

- [ ] **Step 3: Smoke with `--no-kube`**

```bash
rm -rf _test_projects/test-phase4-optout
_bin/skel-gen-ai --no-input --static --no-kube _test_projects/test-phase4-optout python-fastapi-skel "Items API"
# --static skips Ollama; --no-kube skips Phase 4. Expected: exits 0, no deploy/helm/ created by phase 4.
```

Note: When `--static` is passed, `skel-gen-ai` delegates to `skel-gen-static` which doesn't run any phase. Skip this test if `--static` forces an early return.

- [ ] **Step 4: Commit**

```bash
git add _bin/skel-gen-ai
git commit -m "Wire Phase-4 Kubernetes lifecycle into skel-gen-ai after the service test-fix loop. New flags: --no-kube (opt-out), --keep-kube (leave cluster up), --kube-fix-timeout N. On failure, print re-entry hint and exit non-zero without rolling back service code."
```

---

## Task 11: Idempotency + override-preservation smoke

**Files:**
- Modify: `_bin/skel-test-kube-phase` — add idempotency + overrides tests

**Rationale:** Acceptance criteria 3 + 4 from the spec must be enforced by the smoke runner.

- [ ] **Step 1: Add tests to the smoke**

After the existing AI block in `_bin/skel-test-kube-phase`:

```python
# Idempotency: running bootstrap twice should be a no-op for sync
print("[kube-phase] idempotency check")
result2 = run_kubernetes_phase(
    client=None, wrapper_dir=TEST_DIR, project_yml=None,
    skip_kind=True, skip_ai=True,
)
if not result2.ok:
    print(f"[kube-phase] FAIL: second run: {result2.error}", file=sys.stderr)
    return 1

# Override preservation: drop a user file under overrides/; sync must not touch it
print("[kube-phase] override preservation")
marker = TEST_DIR / "deploy" / "helm" / "templates" / "overrides" / "marker.yaml"
marker.write_text("# user\n")
for _ in range(3):
    run_kubernetes_phase(
        client=None, wrapper_dir=TEST_DIR, project_yml=None,
        skip_kind=True, skip_ai=True,
    )
if not marker.exists() or marker.read_text() != "# user\n":
    print(f"[kube-phase] FAIL: override marker was disturbed", file=sys.stderr)
    return 1
```

- [ ] **Step 2: Run**

```bash
_bin/skel-test-kube-phase
```

Expected: static + idempotency + override checks all green.

- [ ] **Step 3: Commit**

```bash
git add _bin/skel-test-kube-phase
git commit -m "Extend test-kube-phase with idempotency (second static run is a no-op) and overrides/ preservation (user marker survives 3 consecutive sync-equivalents). Enforces Phase 7 acceptance criteria 3 + 4."
```

---

## Task 12: Makefile targets + PHONY

**Files:**
- Modify: `Makefile`

**Rationale:** Surface the new smokes to `make help` and CI.

- [ ] **Step 1: Ensure all three targets are present**

Confirm (or add) in `Makefile`:

```make
test-kube-layout: ## Smoke: helm-gen 3-tier layout
	@_bin/skel-test-kube-layout

test-kube-phase: ## Smoke: run_kubernetes_phase() static + (AI if Ollama up) + idempotency
	@_bin/skel-test-kube-phase

test-kube-e2e: ## Opt-in: real kind cluster + helm install + health smoke
	@_bin/skel-test-kube-e2e

test-kube-phase-ai: ## Force AI pass (requires Ollama)
	@OLLAMA_URL=$${OLLAMA_URL:-http://localhost:11434} _bin/skel-test-kube-phase
```

Add all four to `.PHONY`.

- [ ] **Step 2: `make help | grep kube`**

Expected: four lines, one per target, with descriptions.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "Add Makefile targets: test-kube-layout, test-kube-phase, test-kube-phase-ai, test-kube-e2e. All flagged in .PHONY; opt-in targets skip cleanly when tooling missing (exit 2)."
```

---

## Task 13: Docs + rule-file sync

**Files:**
- Modify: `CLAUDE.md`
- Modify: `/AGENTS.md`
- Modify: `_docs/JUNIE-RULES.md`
- Modify: `_docs/LLM-MAINTENANCE.md`
- Modify: `ROADMAP.md`
- Modify: `CHANGELOG.md`

**Rationale:** Cross-agent rule sync + move Phase 7 into "Shipped". Do this ONLY after Tasks 1–12 are merged and green.

- [ ] **Step 1: `ROADMAP.md`**

Move Phase 7 section from open to shipped (same treatment as Phase 5 / Phase 6). Add Phase 7 row to the "Shipped" summary table. Update "Suggested order" to mark Phase 7 as `(DONE)`.

- [ ] **Step 2: `CHANGELOG.md`**

Add `## [2026-04-DD] — Phase 7: Whole-project Kubernetes & Helm lifecycle` entry near the top, summarising:
- `./project kube bootstrap/sync/diff/e2e` (via skel-deploy)
- 3-tier layout (`_generated/`, `_managed/`, `overrides/`)
- `_skels/_common/manifests/_kubernetes.py` (Tier-2 AI dispatch)
- `run_kubernetes_phase` + `_kube_diagnose` + fix loop
- New smokes: `make test-kube-layout / test-kube-phase / test-kube-phase-ai / test-kube-e2e`
- `skel-gen-ai` / `skel-add` gained `--no-kube` / `--keep-kube` / `--kube-fix-timeout`

- [ ] **Step 3: `CLAUDE.md`**

Add a new subsection under "6.*" titled "Phase 4 — Kubernetes lifecycle (`./project kube`)" summarising the 3-tier layout, the four subcommands, the `--no-kube` escape hatch, and the "never hand-edit `_generated/` or `_managed/*`" rule.

- [ ] **Step 4: `/AGENTS.md`**

Same content as CLAUDE.md but in the agents-neutral tone. Cross-reference CLAUDE.md.

- [ ] **Step 5: `_docs/JUNIE-RULES.md`**

Add a "Kubernetes lifecycle" section alongside the existing ones.

- [ ] **Step 6: `_docs/LLM-MAINTENANCE.md`**

Document:
- How to add a new tech to `DISPATCH` in `_kubernetes.py`.
- How to add a new per-file prompt + dispatch it.
- The fix-loop format (`===FILE:===` blocks).
- How to debug a kind E2E failure (`kubectl logs`, `helm template`, `./project kube e2e --keep-kube`).

- [ ] **Step 7: Self-verify**

```bash
make test-kube-layout
make test-kube-phase
# make test-kube-e2e  # only if kind installed
```

All green.

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md AGENTS.md _docs/JUNIE-RULES.md _docs/LLM-MAINTENANCE.md ROADMAP.md CHANGELOG.md
git commit -m "Phase 7 docs + rule-file sync: move Phase 7 to Shipped in ROADMAP, add CHANGELOG entry, document 3-tier layout + ./project kube workflow in CLAUDE.md/AGENTS.md/JUNIE-RULES.md/LLM-MAINTENANCE.md."
```

---

## Self-review checklist

- [x] Every spec decision has a task:
  - Tier-1 relocation → Task 1
  - `_kube_diagnose` → Task 2
  - `_kubernetes.py` manifest → Task 3
  - `run_kubernetes_phase` skeleton → Task 4
  - AI Tier-2 generation → Task 5
  - kind E2E → Task 6
  - Fix loop → Task 7
  - `skel-deploy` subcommands → Task 8
  - `./project kube` forwarder → Task 9
  - `skel-gen-ai` wire point → Task 10
  - Idempotency + override preservation → Task 11
  - Makefile + docs → Tasks 12, 13
- [x] No `TBD` / `TODO` / `similar to Task N`.
- [x] Type consistency: `KubernetesResult`, `run_kubernetes_phase`, `_kube_diagnose`, `_ask_ollama_for_kubernetes`, `_ask_ollama_to_fix_kubernetes`, `_kind_cluster`, `_helm_install_and_wait`, `_smoke_health`, `_tree_diff` used identically across tasks.
- [x] Every code-touching step shows the code.
- [x] Each task ends with a commit.

---

## Execution notes

- **Kind + docker are required** from Task 6 onward. Developers on
  machines without a Docker daemon can run Tasks 1–5 and Tasks 8–11
  with `skip_kind=True`; Task 6's smoke reports exit 2 when tools
  are missing.
- **Ollama is required** for real validation of Task 5 and the fix
  loop in Task 7. The smokes gracefully degrade (static-only path)
  when `_ollama_up()` returns False.
- **Expected total wall-clock** for a clean run through Tasks 1–13:
  ~6–10 hours of implementation + ~2 hours of real E2E validation
  (multiple `kind create/delete` cycles are the bottleneck).
