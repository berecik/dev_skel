# Phase 7 — Whole-project Kubernetes & Helm lifecycle (AI-assisted)

**Date:** 2026-04-19
**Status:** Design approved, pending implementation plan
**Roadmap reference:** `ROADMAP.md` → Phase 7

---

## Goal

Manage Kubernetes/Helm definitions for the entire wrapper project as
one deployable unit, AI-assisted. Extend the Phase-5 static Helm
baseline with a per-service AI tier, wire the lifecycle into
`skel-gen-ai` / `skel-add` after the integration phase, and provide
drift-safe `sync` / `diff` commands at the wrapper level.

## Non-goals

- Full AI-authored chart (non-deterministic). Kept out of scope —
  Phase 5's deterministic baseline stays the anchor.
- Cloud-provider-specific resources (IRSA, Workload Identity, etc).
  Users add those via `overrides/`.
- Multi-cluster / GitOps integration. Separate future phase.

---

## Decisions (summary)

| Axis | Decision |
| ---- | -------- |
| Scope | **Level B** — Tier-2 per-service AI add-ons on top of Phase 5 Tier-1 static baseline. |
| Content layout | **File-level separation** — `deploy/helm/templates/{_generated,_managed,overrides}/`. Managed trees wiped+rewritten; `overrides/` never touched. |
| E2E bar | **Always-`kind` on the hot path.** `kind` is a hard dependency unless `--no-kube` is passed. |
| AI manifest organization | **Single shared** `_skels/_common/manifests/_kubernetes.py` dispatching on `service.tech`. |
| Wire point | **New fourth phase** in `skel-gen-ai` after the service test-fix loop converges. |
| CLI | `./project kube` is a **thin forwarder** to `_bin/skel-deploy` (new subcommands: `bootstrap`, `sync`, `diff`, `e2e`). |
| Fix-loop input | **Structured diagnostic bundle** (`_kube_diagnose()` in `skel_ai_lib.py`). |

---

## Architecture

```
skel-gen-ai / skel-add
  Phase 1  per-target AI generation          (existing)
  Phase 2  integration phase                 (existing)
  Phase 3  service test-fix loop             (existing)
  Phase 4  kubernetes phase                  (NEW)
             a. skel-deploy helm-gen         → Tier-1 static
             b. _kubernetes.py AI dispatch   → Tier-2 per-service add-ons
             c. kind up + helm install + /api/health smoke
             d. fix-loop on failure          (Tier-2 edits only)
             e. kind down                    (unless --keep-kube)
```

Three tiers share `deploy/helm/`:

```
deploy/helm/
  Chart.yaml                   ← Tier-1 (regenerated)
  values.yaml
  values-local.yaml
  values-cloud.yaml
  templates/
    _generated/                ← Tier-1, wiped + rewritten by helm-gen
      ingress.yaml
      namespace.yaml
      postgres.yaml
      service-deployment.yaml
    _managed/<svc>/            ← Tier-2, wiped + rewritten by AI
      migration-job.yaml
      configmap.yaml
      hpa.yaml
      ...
    overrides/                 ← Tier-3, never touched
      <user-authored>.yaml
```

Helm's natural name-collision merge rules let `overrides/` beat either
managed tree — no in-file markers, no regex splicing.

---

## Components (what gets added)

### 1. `_skels/_common/manifests/_kubernetes.py`

New AI manifest, single file. Keys:

- `dispatch: dict[tech, list[filename]]` — which Tier-2 files each
  `service.tech` gets (see "Dispatch table" below).
- `system_prompt: str` — governs all Tier-2 generation.
- `file_prompts: dict[filename, str]` — per-file contract (inputs,
  required shape, Helm template variables available).
- `fix_prompt: str` — used by the fix-loop.

**Dispatch table (initial):**

| `service.tech`        | Tier-2 files                                               |
| --------------------- | ---------------------------------------------------------- |
| `python-django`       | `migration-job.yaml`, `configmap.yaml`, `hpa.yaml`         |
| `python-django-bolt`  | `migration-job.yaml`, `configmap.yaml`, `hpa.yaml`         |
| `python-fastapi`      | `configmap.yaml`, `hpa.yaml`                               |
| `python-flask`        | `configmap.yaml`, `hpa.yaml`                               |
| `java-spring`         | `configmap.yaml`, `hpa.yaml`, `jvm-env.yaml`               |
| `rust-actix`          | `configmap.yaml`, `hpa.yaml`                               |
| `rust-axum`           | `configmap.yaml`, `hpa.yaml`                               |
| `next-js`             | `configmap.yaml`, `hpa.yaml`                               |
| `ts-react`            | `nginx-configmap.yaml`                                     |
| `flutter`             | *(skipped — not cluster-deployed)*                         |

### 2. `skel_ai_lib.run_kubernetes_phase()`

```python
def run_kubernetes_phase(
    client,
    wrapper_dir: Path,
    project_yml: dict,
    *,
    fix_timeout_m: int = 30,
    keep_kind: bool = False,
    skip_kind: bool = False,
) -> KubernetesResult: ...
```

Runs steps 4a–4e above. Reuses `run_test_and_fix_loop`'s loop shape
but with the kube diagnostic bundle + managed-tree-only write scope.

### 3. `skel_ai_lib._kube_diagnose()`

```python
def _kube_diagnose(wrapper_dir: Path, namespace: str) -> str: ...
```

Output (deterministic, ≤300 lines):

```
FAILING_RESOURCES:
  - pod/items-api-abc123  status=CrashLoopBackOff   restarts=4
  - job/items-api-migrate status=Failed             age=2m

EVENTS (last 20):
  Warning FailedScheduling ...

DESCRIBE (truncated to 40 lines each):
  === pod/items-api-abc123 ===
  ...

LOGS (last 50 lines per failing container):
  === items-api-abc123/api ===
  ...
```

### 4. `_bin/skel-deploy` — new subcommands

- `bootstrap <wrapper>` — Tier-1 + Tier-2 + kind E2E. Called from
  `skel-gen-ai` / `skel-add` Phase 4. Flags: `--no-kube`,
  `--keep-kube`, `--fix-timeout N`.
- `sync <wrapper>` — wipe + regenerate both managed trees. Prompts
  for confirmation unless `--yes`. Runs `helm lint` + `kubeconform`
  at the end. `--e2e` re-runs the full kind E2E.
- `diff <wrapper>` — dry-run. Writes both managed trees to a temp
  dir, runs `helm template` on the current tree and on the
  dry-run tree, emits a unified diff. `--rendered` compares
  fully-rendered YAML; default compares raw files.
- `e2e <wrapper>` — standalone kind spin-up + install + health
  smoke. No regen.

### 5. `./project kube` wrapper forwarder

Added to `_skels/_common/common-wrapper.sh`. Pure bash
dispatch — forwards `kube <cmd>` to
`python3 "$DEV_SKEL_ROOT/_bin/skel-deploy" <cmd> "$SCRIPT_DIR"`.
Uses the same dev_skel-root auto-detect logic as `./ai` /
`./backport`. If dev_skel is unreachable, exits 1 with an
actionable pointer.

### 6. `skel-gen-ai` / `skel-add` wiring

After `run_test_and_fix_loop` returns green, if `--no-kube` was not
passed, call `run_kubernetes_phase(..., fix_timeout_m=30)`. On
failure, print the final diagnostic bundle + exit non-zero (user
can re-run `./project kube sync --e2e` later without regenerating
service code).

Phase 4 is AI-only: `skel-gen-static` does **not** run it. A user
who wants K8s on a statically-generated wrapper runs
`./project kube bootstrap` explicitly after generation.

---

## Data flow

**Generation hot path:**

```
skel-gen-ai
  ├── Phase 1 (per-target)
  ├── Phase 2 (integration)
  ├── Phase 3 (service test-fix)
  └── Phase 4 (kubernetes) ─── skel_ai_lib.run_kubernetes_phase
                                 ├── skel-deploy helm-gen            (Tier-1)
                                 ├── _kubernetes.py dispatch         (Tier-2)
                                 ├── helm lint + kubeconform
                                 ├── kind create cluster (temp)
                                 ├── helm install --wait
                                 ├── curl /api/health per backend
                                 ├── fix-loop on fail
                                 │     └── _kube_diagnose() → LLM → Tier-2 rewrite
                                 └── kind delete cluster
```

**Sync path** (`./project kube sync`):

```
read dev_skel.project.yml
write Tier-1 + Tier-2 to temp dir
diff vs. current tree
prompt (unless --yes)
wipe _generated/ + _managed/
write from temp dir
preserve overrides/
run helm lint + kubeconform
  if --e2e: kind spin-up + install + health smoke
```

**Diff path** (`./project kube diff`):

```
write Tier-1 + Tier-2 to temp dir
default:   tree diff temp_dir ↔ deploy/helm/templates/{_generated,_managed}/
--rendered: helm template <current>  vs.  helm template <temp>  →  unified diff
```

---

## Error handling

- **`kind` or `docker` missing.** Hard fail at the start of Phase 4
  with an install hint (`brew install kind` / `apt install
  docker.io kind`). `--no-kube` skips the cluster portion; `helm
  lint` + `kubeconform` still run. A user who later installs
  `kind` can backfill the cluster validation with
  `./project kube e2e`.
- **Fix-loop timeout.** After `fix_timeout_m` (default 30 min),
  print the final diagnostic bundle, leave the temp cluster deleted,
  exit non-zero. Tier-1 + Tier-2 files remain on disk so
  `./project kube sync` can resume.
- **AI tries to write outside `_managed/<svc>/`.** Rejected at write
  time (path-resolve guard, same pattern as
  `dev_skel_refactor_runtime`). Counts as a failed fix iteration;
  counter advances.
- **Override collision with managed filename.** Helm's name-based
  override wins. A warning is logged ("overrides/x.yaml shadows
  managed _generated/x.yaml") but no error.
- **`dev_skel.project.yml` lacks a service's `tech` field.**
  Dispatch falls through to the empty add-on list; service gets
  Tier-1 only. Emit a warning.
- **Concurrent `./project kube sync` runs.** Single per-wrapper
  `.ai/kube.lock` (O_CREAT|O_EXCL), same pattern as `./ai apply`.

---

## Testing

### `make test-kube-phase` (new)

Fast smoke (no LLM). Exits 2 ("skipped") when `kind` or `docker`
is missing. Artifact lives at `_test_projects/test-kube-phase/`.

Verifies:

1. `make gen-stack-web NAME=_test_projects/test-kube-phase`
   generates the wrapper (no K8s phase — static stack gen).
2. `skel-deploy bootstrap --no-kube _test_projects/test-kube-phase`
   writes both managed trees. Assert file layout:
   - `deploy/helm/templates/_generated/*.yaml` present.
   - `deploy/helm/templates/_managed/items_api/configmap.yaml`
     + `hpa.yaml` present.
   - `deploy/helm/templates/_managed/web_ui/nginx-configmap.yaml`
     present.
   - `deploy/helm/templates/overrides/` exists, empty.
3. `helm lint deploy/helm/` exits 0.
4. `kubeconform` on all managed YAML exits 0.
5. `./project kube diff` reports no changes (idempotent).
6. Touch `deploy/helm/templates/overrides/marker.yaml`; rerun
   `./project kube sync --yes`; assert `overrides/marker.yaml`
   still present (drift-safe).

### `make test-kube-e2e` (opt-in, slow)

- Actually spins up `kind`. `helm install`, wait for pods ready,
  curl `/api/health` on each backend, `helm uninstall`,
  `kind delete`.
- ~5–10 min. Gated on `kind` being installed — skips (exit 2)
  otherwise. Run manually or in CI behind a `KUBE_E2E=1` guard.

### `make test-kube-phase-ai` (opt-in, needs Ollama)

- Real AI Tier-2 generation with `qwen3-coder:30b`. Same scenario
  as `test-kube-phase` but exercises `_kubernetes.py` prompts.
  Mirrors `make test-ai-generators` gating (exit 2 when Ollama
  unreachable).

---

## File layout summary

**New files:**

- `_skels/_common/manifests/_kubernetes.py` — AI manifest.
- `docs/superpowers/specs/2026-04-19-phase7-kubernetes-lifecycle-design.md` — this doc.
- `_bin/skel-test-kube-phase` — fast smoke runner.
- `_bin/skel-test-kube-e2e` — opt-in kind E2E.

**Modified files:**

- `_bin/skel-deploy` — new subcommands (`bootstrap`, `sync`, `diff`, `e2e`).
- `_bin/skel_ai_lib.py` — `run_kubernetes_phase`, `_kube_diagnose`.
- `_bin/skel-gen-ai` — Phase-4 dispatch after test-fix.
- `_bin/skel-add` — same hook (uses existing `skel-gen-ai --skip-base`).
- `_skels/_common/common-wrapper.sh` — emit `./project kube` forwarder.
- `Makefile` — `test-kube-phase`, `test-kube-phase-ai`, `test-kube-e2e`.
- `ROADMAP.md` — mark Phase 7 items as implemented, move to "Shipped".
- `CHANGELOG.md` — Phase 7 entry.
- `CLAUDE.md`, `/AGENTS.md`, `_docs/JUNIE-RULES.md`,
  `_docs/LLM-MAINTENANCE.md` — cross-agent rules for the new phase
  + `./project kube` workflow.

---

## Out-of-scope notes (deferred)

- Helmfile / multi-chart orchestration.
- ArgoCD / Flux manifests.
- Service mesh (Linkerd/Istio) sidecar injection.
- Cloud provider-specific annotations (auto-scaling group tags,
  IRSA bindings).
- Secrets management beyond the `jwt-secret` the Phase-5 template
  already emits.

These land in a Phase 8 if/when users ask for them.

---

## Acceptance criteria

Phase 7 is "done" when:

1. `make test-kube-phase` passes on a clean checkout with `kind` +
   `docker` + `helm` + `kubeconform` installed.
2. `_bin/skel-gen-ai` with a backend skel writes both managed
   trees and passes the kind E2E during generation.
3. `./project kube sync` + `./project kube diff` round-trip is
   idempotent on a freshly-generated wrapper (diff empty after sync).
4. User-authored file in `overrides/` survives three consecutive
   `./project kube sync --yes` runs.
5. `ROADMAP.md` + `CHANGELOG.md` + all cross-agent rule files
   updated to reflect shipped behaviour.
