# Kubernetes Cross-Stack Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run cross-stack React integration tests against backends deployed to Kubernetes (k3s on paul), starting with FastAPI + React, with a local CI command.

**Architecture:** Build Docker images locally, push to k3s via `k3s ctr images import`, deploy via Helm charts (existing `skel-deploy helm-gen` + `helm upgrade --install`), expose services via NodePort, run the same HTTP exercise + Playwright E2E against the k8s-deployed services. Devcontainer tests use the same BackendSpec pattern but run inside `docker compose` instead of bare processes.

**Tech Stack:** k3s (v1.33), Helm 3, Docker, crictl, kubectl, existing `_bin/skel-deploy`, `_bin/_frontend_backend_lib.py`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `_bin/skel-test-k8s-react-fastapi` | K8s cross-stack test: FastAPI + React on k3s |
| `_bin/skel-test-k8s-common.py` | Shared k8s test helpers (build, push, deploy, cleanup) |
| `_bin/skel-test-devcontainer-react-fastapi` | Devcontainer cross-stack test: FastAPI + React |
| `Makefile` (modify) | Add `test-k8s-react-fastapi`, `test-k8s-cross-stack`, `test-devcontainer-*` targets |
| `.github/workflows/maintenance.yml` (modify) | Optional: add k8s test step for self-hosted runner |

---

### Task 1: K8s Test Helper Module

**Files:**
- Create: `_bin/skel-test-k8s-common.py`

- [ ] **Step 1: Write the k8s helper module with core functions**

```python
"""Shared helpers for Kubernetes cross-stack tests.

Functions:
- docker_build(service_dir, image_tag) -> build Docker image
- k3s_import(image_tag, host) -> push image to k3s via SSH + ctr import
- helm_deploy(wrapper_dir, namespace, values_overrides) -> helm upgrade --install
- wait_for_pods(namespace, timeout_s) -> poll until all pods Ready
- get_nodeport(namespace, service_name) -> return the NodePort number
- helm_teardown(namespace) -> helm uninstall + kubectl delete ns
"""
```

The module provides:
- `docker_build(service_dir: Path, tag: str) -> None` — runs `docker build -t {tag} {service_dir}`
- `k3s_import(tag: str, host: str = "paul") -> None` — `docker save {tag} | ssh {host} k3s ctr images import -`
- `helm_deploy(wrapper: Path, namespace: str, overrides: dict) -> None` — calls `skel-deploy up` or `helm upgrade --install` with `--set service.type=NodePort`
- `wait_for_pods(namespace: str, timeout_s: int = 120) -> bool` — polls `kubectl get pods -n {ns}` until all Ready
- `get_nodeport(namespace: str, svc: str) -> int` — parses `kubectl get svc -n {ns} {svc} -o jsonpath='{.spec.ports[0].nodePort}'`
- `helm_teardown(namespace: str) -> None` — `helm uninstall -n {ns}` + `kubectl delete ns {ns}`

- [ ] **Step 2: Verify module imports cleanly**

Run: `python3 -c "import sys; sys.path.insert(0,'_bin'); import skel_test_k8s_common; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add _bin/skel-test-k8s-common.py
git commit -m "feat: add k8s cross-stack test helper module"
```

---

### Task 2: K8s FastAPI + React Test Script

**Files:**
- Create: `_bin/skel-test-k8s-react-fastapi`

- [ ] **Step 1: Write the test script**

The script follows this flow:
1. Generate wrapper (FastAPI + React) via `skel-gen-static`
2. Run `skel-deploy helm-gen` to create Helm chart
3. Build Docker images for both services
4. Import images to k3s via SSH (`docker save | ssh paul k3s ctr images import -`)
5. Create namespace `test-k8s-react-fastapi`
6. `helm upgrade --install` with NodePort service type + image overrides
7. Wait for pods Ready
8. Get NodePort, construct `backend_url = http://paul:{nodeport}`
9. Run the standard HTTP exercise (`exercise_items_api`)
10. Run order workflow (`exercise_orders_api`)
11. Cleanup: helm uninstall + delete namespace

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x _bin/skel-test-k8s-react-fastapi
python3 -c "import py_compile; py_compile.compile('_bin/skel-test-k8s-react-fastapi', doraise=True)"
```

- [ ] **Step 3: Test dry-run (verify generation + helm chart creation)**

```bash
_bin/skel-test-k8s-react-fastapi --dry-run
```
Expected: generates wrapper, creates helm chart, prints what would be deployed, exits without deploying.

- [ ] **Step 4: Test full run against paul's k3s**

```bash
_bin/skel-test-k8s-react-fastapi --keep
```
Expected: deploys to k3s, exercises HTTP API, all checks pass, leaves resources for inspection.

- [ ] **Step 5: Commit**

```bash
git add _bin/skel-test-k8s-react-fastapi
git commit -m "feat: add k8s cross-stack test (FastAPI + React on k3s)"
```

---

### Task 3: Devcontainer FastAPI + React Test Script

**Files:**
- Create: `_bin/skel-test-devcontainer-react-fastapi`

- [ ] **Step 1: Write the devcontainer test script**

The script follows this flow:
1. Generate wrapper (FastAPI + React) via `skel-gen-static`
2. Start services via `docker compose -f docker-compose.yml up -d` (wrapper-level)
3. Wait for backend to be reachable on the compose-mapped port
4. Run the standard HTTP exercise
5. Run order workflow
6. Cleanup: `docker compose down -v`

This is simpler than k8s — it uses the existing `docker-compose.yml` that `common-wrapper.sh` generates.

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x _bin/skel-test-devcontainer-react-fastapi
python3 -c "import py_compile; py_compile.compile('_bin/skel-test-devcontainer-react-fastapi', doraise=True)"
```

- [ ] **Step 3: Test full run**

```bash
_bin/skel-test-devcontainer-react-fastapi --keep
```
Expected: starts Docker Compose services, exercises HTTP API, all checks pass.

- [ ] **Step 4: Commit**

```bash
git add _bin/skel-test-devcontainer-react-fastapi
git commit -m "feat: add devcontainer cross-stack test (FastAPI + React)"
```

---

### Task 4: Makefile Targets

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add k8s and devcontainer test targets**

```makefile
# K8s cross-stack tests (requires kubectl + k3s cluster)
test-k8s-react-fastapi: ## K8s cross-stack test (FastAPI + React on k3s)
	@echo "$(GREEN)=== K8s: React + FastAPI ===$(NC)"
	@_bin/skel-test-k8s-react-fastapi

test-k8s-react-fastapi-keep: ## Same, but leave k8s resources deployed
	@_bin/skel-test-k8s-react-fastapi --keep

test-k8s-cross-stack: ## Run all K8s cross-stack tests
	@echo "$(GREEN)=== Running all K8s cross-stack tests ===$(NC)"
	@$(MAKE) test-k8s-react-fastapi
	@echo "$(GREEN)All K8s cross-stack tests passed.$(NC)"

# Devcontainer cross-stack tests (requires Docker)
test-devcontainer-react-fastapi: ## Devcontainer cross-stack test (FastAPI + React)
	@echo "$(GREEN)=== Devcontainer: React + FastAPI ===$(NC)"
	@_bin/skel-test-devcontainer-react-fastapi

test-devcontainer-cross-stack: ## Run all devcontainer cross-stack tests
	@echo "$(GREEN)=== Running all devcontainer cross-stack tests ===$(NC)"
	@$(MAKE) test-devcontainer-react-fastapi
	@echo "$(GREEN)All devcontainer cross-stack tests passed.$(NC)"
```

- [ ] **Step 2: Add targets to .PHONY list**

- [ ] **Step 3: Verify targets exist**

Run: `make help | grep -E "k8s|devcontainer"`
Expected: shows the new targets

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "feat: add k8s and devcontainer test Makefile targets"
```

---

### Task 5: Helm Chart NodePort Override

**Files:**
- Modify: `_skels/_common/helm/templates/service.yaml` (or values)

- [ ] **Step 1: Ensure the Helm chart supports NodePort service type**

The existing Helm chart generates ClusterIP services. For k8s tests we need NodePort. Add a `values.yaml` override:

```yaml
# In values.yaml or via --set:
services:
  <service-id>:
    type: NodePort    # default: ClusterIP
    nodePort: 30080   # optional: specific port
```

Update the service template to use `{{ .Values.services.<svc>.type | default "ClusterIP" }}`.

- [ ] **Step 2: Verify helm lint passes with NodePort override**

```bash
helm lint deploy/helm/ --set services.backend.type=NodePort
```

- [ ] **Step 3: Commit**

```bash
git add _skels/_common/helm/
git commit -m "feat: support NodePort service type in Helm charts for k8s tests"
```

---

### Task 6: End-to-End Verification

- [ ] **Step 1: Run k8s test against paul**

```bash
make test-k8s-react-fastapi
```
Expected: ALL CHECKS PASSED

- [ ] **Step 2: Run devcontainer test locally**

```bash
make test-devcontainer-react-fastapi
```
Expected: ALL CHECKS PASSED

- [ ] **Step 3: Run full cross-stack suite to verify no regressions**

```bash
make test-cross-stack
```
Expected: 19/19 PASS (no regressions from k8s/devcontainer changes)

- [ ] **Step 4: Final commit**

```bash
git commit -m "test: verify k8s + devcontainer cross-stack tests pass"
```

---

## Prerequisites

- kubectl configured to reach paul's k3s cluster (`kubectl cluster-info` works)
- SSH access to paul (`ssh paul` works)
- Docker installed locally (`docker build` works)
- Helm 3 installed (`helm version` works)

## Extension Points

After FastAPI + React works on k8s, adding more backends follows the same pattern:
1. Copy `skel-test-k8s-react-fastapi` → `skel-test-k8s-react-<backend>`
2. Change `BACKEND_SKEL`, `BackendSpec`, and Docker build context
3. Add Makefile target
4. Add to `test-k8s-cross-stack` list

The devcontainer tests similarly extend by copying the FastAPI script.
