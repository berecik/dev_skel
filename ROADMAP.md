# Dev Skel Roadmap

Dev Skel generates **whole multi-service projects where every service
ships with its own in-service code agent**. Phases 1–4 are shipped;
this document tracks the remaining phases. See
[`CHANGELOG.md`](CHANGELOG.md) for the full history of delivered work.

---

## Shipped (2026-04) — summary

| Phase | What | Key deliverables |
| ----- | ---- | ---------------- |
| 1 | AI generation pipeline | 12 manifests, INTEGRATION_MANIFEST, auto-retry, multi-phase context, critique loop, `qwen3-coder:30b` |
| 2 | Project metadata | `dev_skel.project.yml`, `./services list\|info\|set-active`, `./run-dev-all`, pagination compat |
| 3 | Cross-service contracts | OpenAPI 3.1 spec (14 ops), `skel-contracts` CLI (export/validate/diff/info) |
| 4 | Observability baseline | `/api/health` (all backends), `LOG_FORMAT`, `OTEL_*`, Docker Compose `--profile observability` |
| 5 | Kubernetes & Helm | Helm chart template, `skel-deploy` CLI (helm-gen/up/down/status), `./kube` wrapper, values profiles (local/cloud) |
| 6 | Project-level UX | `./project test\|lint\|build\|graph`, `./env use dev\|staging\|prod`, `make gen-stack-web`/`gen-stack-enterprise`, `make test-project-ux` smoke |
| — | Infrastructure | 12 skeletons, unified schema (items+categories+auth+state), per-service docker-compose, `./ai`+`./backport`, CI pipeline, Skeleton Design Guide |

Full details: [`CHANGELOG.md`](CHANGELOG.md)

---

## ~~Phase 5 — Kubernetes & Helm~~ (DONE)

**Shipped 2026-04.** Helm chart generation from `dev_skel.project.yml`.

- [x] Helm chart templates at `_skels/_common/helm/` (Deployment +
      Service per backend, Postgres StatefulSet, Ingress, Secrets,
      health test hooks).
- [x] `_bin/skel-deploy` CLI: `helm-gen` (generate chart from
      project metadata), `up` (helm upgrade --install), `down`
      (helm uninstall), `status` (release + pod status).
- [x] `./kube` wrapper script in every generated wrapper.
- [x] Three values profiles: `values.yaml` (production), 
      `values-local.yaml` (minikube/kind), `values-cloud.yaml` (cloud).
- [x] K8s-safe naming (underscores → hyphens).
- [x] `helm lint` passes cleanly.

---

## ~~Phase 6 — Project-level UX~~ (DONE)

**Shipped 2026-04.** Wrapper-level UX that treats the multi-service
project as a single product.

- [x] `./project test` / `lint` / `build` — fan out across services
      with a colour-coded aggregated summary
      (`_skels/_common/common-wrapper.sh`).
- [x] `./project graph` — emit a Mermaid (`graph TD`) or DOT
      (`--dot`) service dependency diagram from
      `dev_skel.project.yml` + `_shared/service-urls.env`.
- [x] `./env use dev|staging|prod` + `./env current` — switch
      environment profiles (`.env.<profile>` → `.env`), persisted
      in `_shared/active-env`.
- [x] Opinionated stack generators — `make gen-stack-web`
      (FastAPI + React), `make gen-stack-enterprise`
      (Spring + Actix + React).
- [x] Smoke test `make test-project-ux` (`_bin/skel-test-project-ux`)
      exercises both stacks end-to-end; artifacts land in
      `_test_projects/` per the mandatory test-location rule.

---

## Phase 7 — Whole-project Kubernetes & Helm lifecycle

**Goal:** Manage Kubernetes/Helm definitions for the entire wrapper
project as one deployable unit (AI create + check + update).

- [ ] AI-assisted lifecycle generates and validates baseline K8s + Helm
      definitions for all services from `dev_skel.project.yml`.
- [ ] Run the Kubernetes/Helm lifecycle from `skel-gen` and `skel-add`
      after the integration phase.
- [ ] `./project kube sync` updates existing definitions when services
      are added/removed/renamed or env contracts change.
- [ ] Drift-safe updates: preserve user overrides and regenerate only
      managed sections/files.
- [ ] `./project kube diff` reports what will change before writing.
- [ ] After the Kubernetes phase, run E2E + integration tests and loop
      auto-fixes until no issues remain.

---

## Suggested order

1. ~~**Phase 5** — Kubernetes / Helm.~~ (DONE)
2. ~~**Phase 6** — project-level UX + stack generators.~~ (DONE)
3. **Phase 7** — whole-project K8s/Helm lifecycle (AI-assisted).
