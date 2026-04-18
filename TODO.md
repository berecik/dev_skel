# Dev Skel — TODO

Actionable follow-ups. See [`ROADMAP.md`](ROADMAP.md) for the
forward-looking phases and [`CHANGELOG.md`](CHANGELOG.md) for
everything shipped.

---

## ~~Section 1 — Kubernetes & Helm~~ (DONE)

**Shipped.** Helm chart templates, `skel-deploy` CLI, `./kube`
wrapper, three values profiles, K8s-safe naming. `helm lint` clean.

---

## Section 2 — Project-level UX (Roadmap Phase 6)

### 2.1 `./project test` / `lint` / `build` with aggregated summary

**Scenario.** Fan out across services, aggregate exit codes, print
colour-coded summary with per-service timings.

### 2.2 `./project graph` — service dependency diagram

**Scenario.** Read `dev_skel.project.yml` + `_shared/service-urls.env`,
emit Mermaid diagram to stdout.

### 2.3 `./env use dev|staging|prod`

**Scenario.** Switch active environment profile.

### 2.4 Stack generators (`gen-stack-web`, `gen-stack-enterprise`)

**Scenario.** High-level Make targets that generate multi-service
projects in one command:
- `gen-stack-web`: FastAPI + React + Postgres
- `gen-stack-enterprise`: Spring + Actix auth + React + Kafka

---

## Section 3 — Whole-project Kubernetes & Helm lifecycle (Roadmap Phase 7)

### 3.1 `./project kube init` — create baseline definitions

**Scenario.** Use AI to generate and validate initial Kubernetes +
Helm definitions for all services from `dev_skel.project.yml` as a
single project deployment.

### 3.2 Run lifecycle during generation and add-service flows

**Scenario.** Execute the Kubernetes/Helm lifecycle from `skel-gen`
and `skel-add` after the integration phase.

### 3.3 `./project kube sync` — update existing definitions

**Scenario.** Create/update definitions after service add/remove/rename
or env-contract changes without rewriting unrelated files.

### 3.4 Drift-safe managed updates

**Scenario.** Keep user-customized values while regenerating only
tool-managed sections/files.

### 3.5 `./project kube diff` preflight

**Scenario.** Show what create/update operations will occur before any
files are written.

### 3.6 Post-kubernetes E2E + integration fix loop

**Scenario.** After the Kubernetes phase, run E2E and integration tests
and keep fixing issues until no issues remain.

---

## Section 4 — Documentation polish

### 4.1 Migration guide: legacy `backend-1/` → service-name dirs

### 4.2 Wrapper README "Cookbook" section

### 4.3 Shared database conventions doc

**Files.** New `_docs/SHARED-DATABASE-CONVENTIONS.md` documenting the
canonical `users` + `categories` + `items` + `react_state` schema.

### 4.4 Per-backend runtime OpenAPI at `/docs`

**Why.** Nice-to-have for backend devs. The canonical spec exists;
this adds runtime `/docs` endpoints using per-framework libraries
(springdoc-openapi, utoipa, apispec, etc.).

---

## Suggested execution order

1. **Section 1** — Kubernetes / Helm (Phase 5).
2. **Section 2** — project-level UX (Phase 6).
3. **Section 3** — whole-project K8s/Helm create-or-update workflow (Phase 7).
4. **Section 4** — docs polish (can land any time).
