# Dev Skel Roadmap

Dev Skel generates **whole multi-service projects where every service
ships with its own in-service code agent**. The platform covers
generation, per-service AI refactoring, template ↔ service sync,
cross-stack integration testing, Docker, devcontainers, and a unified
data schema enforced across all 10 backends and both frontends.

This roadmap tracks what's next.

---

## What's shipped (2026-04)

- **12 skeletons** — Python (FastAPI, FastAPI-RAG, Django, Django-Bolt,
  Flask), Java (Spring), Rust (Actix, Axum), Go, Next.js, React/Vite,
  Flutter. All ship Dockerfile + .devcontainer + VERSION + CHANGELOG.
- **10 AI manifests** — every skel except go-skel and
  python-fastapi-rag-skel has a manifest under
  `_skels/_common/manifests/`.
- **Full-stack dialog** — `skel-gen-ai` asks for backend + frontend
  separately (defaults: first items-API backend + `ts-react-skel`),
  then runs 5 Ollama phases. Both halves optional (`--no-backend`,
  `--no-frontend`).
- **Unified data schema** — ALL 10 backends ship the complete
  wrapper-shared API:
  - `/api/auth/register` + `/api/auth/login` (JWT)
  - `/api/items` CRUD + `/api/items/{id}/complete`
  - `/api/categories` CRUD (shared, auth-protected, unique name)
  - `/api/state` per-user key/value store
  - Data model: `user -< item >- category`, `user -< state`
  - `category_id` nullable FK with ON DELETE SET NULL
- **Both frontends** (React + Flutter) ship typed clients for all
  four endpoint families (items, categories, auth, state).
- **Per-service `./ai`** — propose / apply / verify / explain /
  history / undo / upgrade. In-tree (FAISS RAG) and out-of-tree
  (stdlib) modes. Wrapper-level fan-out by default.
- **`./backport` + `./ai upgrade`** — service ↔ template sync with
  semver VERSION bump + CHANGELOG append.
- **Cross-call memory** — JSONL at wrapper + service level.
- **Cross-stack integration tests** — 9 React × backend pairs + 2
  Flutter × backend pairs. Each exercises 23+ HTTP steps: items CRUD
  (9 steps) + categories CRUD (5 steps) + items↔categories FK (4
  steps) + state save/load/delete (5 steps) + vitest smoke +
  Playwright E2E.
- **Shared-DB integration test** — proves every Python backend reads
  the same SQLite via `DATABASE_URL`.
- **Skeleton Design Guide** — `_docs/SKELETON-DESIGN-GUIDE.md` covers
  creating, updating, and maintaining skeletons.
- **CI pipeline** — GitHub Actions runs `./maintenance` on every push
  to master. `make ci-status` / `ci-watch` / `ci-log` via `gh`.

---

## ~~Phase 1 — INTEGRATION_MANIFEST rollout~~ (DONE)

**Shipped 2026-04.** All 10 AI-supported skeletons now ship an
`INTEGRATION_MANIFEST` with sibling-client targets + integration test
targets + a `test_command`. `make test-ai-generators-dry` passes 10/10.

| Skeleton | Integration targets | test_command |
| -------- | ------------------- | ------------ |
| python-django-bolt-skel | 3 (marker + clients + tests) | `./test app/tests/test_integration.py` |
| python-django-skel | 3 | `./test tests/test_integration.py` |
| python-fastapi-skel | 3 | `./test app/tests/test_integration.py` |
| python-flask-skel | 3 | `./test tests/test_integration.py` |
| java-spring-skel | 2 (clients + tests) | `./test` |
| rust-actix-skel | 3 (mod + clients + tests) | `cargo test --test integration` |
| rust-axum-skel | 3 | `cargo test --test integration` |
| next-js-skel | 2 (clients + tests) | `npm test` |
| ts-react-skel | 2 (sibling-info + tests) | `npm test -- --run` |
| flutter-skel | 2 (sibling_info + tests) | `flutter test test/integration_test.dart` |

---

## Phase 2 — Project metadata + orchestration UX

**Goal:** The wrapper has a first-class notion of its services beyond
"directory exists".

- [ ] `dev_skel.project.yml` — per-service entry with `id`, `kind`,
      `tech`, `role`, `ports`. Auto-updated by `gen` / `common-wrapper`.
- [ ] `./services info <id>` / `./services set-active <id>`.
- [ ] `./run dev-all` — start every service in parallel, combined log
      tail, `./stop dev-all` to tear down.
- [ ] Per-service entries in `docker-compose.yml` — today only Postgres
      is declared; add one container per service so `docker compose up`
      boots the whole stack.

---

## Phase 3 — Cross-service contracts

**Goal:** Services share types and API contracts from a single source
of truth.

- [ ] OpenAPI export per backend (`./contracts export` → writes specs
      to `contracts/openapi/<slug>.yaml`).
- [ ] Type-safe codegen (`./contracts gen` → Python Pydantic clients,
      TypeScript fetch clients, Rust `reqwest` clients, Dart clients
      from OpenAPI specs).
- [ ] Contract validation (`./contracts validate` — lint + breaking
      change detection).

---

## Phase 4 — Observability baseline

**Goal:** Every generated service is observable by default.

- [ ] Structured JSON logging with a canonical envelope
      (`timestamp`, `level`, `service`, `trace_id`, `message`).
      `LOG_FORMAT=json|console` env var.
- [ ] OpenTelemetry tracing — propagate `traceparent` across HTTP
      calls. Per-skel OTel SDK init wired into the existing middleware.
- [ ] Docker Compose `--profile observability` that brings up
      otel-collector + Tempo + Grafana.
- [ ] Standardise `/health` + `/ready` endpoints across all backends.

---

## Phase 5 — Kubernetes & Helm

**Goal:** Generate K8s/Helm configs from the same project metadata.

- [ ] `deploy/helm/` umbrella chart with per-service subcharts.
- [ ] `./deploy helm-gen` reads `dev_skel.project.yml` and generates
      Deployments, Services, Ingress, ConfigMaps, Secrets, HPAs.
- [ ] Environment profiles (`dev` / `staging` / `prod`) via
      `values.yaml` / `values.local.yaml`.
- [ ] CI targets: `make ci-build-images`, `ci-push-images`, `ci-deploy`.

---

## Phase 6 — Project-level UX

**Goal:** Treat the wrapper as a single product.

- [ ] `./project test` / `lint` / `build` — fan out across services
      with a colour-coded aggregated summary.
- [ ] `./project graph` — emit a Mermaid/DOT service dependency
      diagram from `dev_skel.project.yml`.
- [ ] `./env use dev|staging|prod` — switch environment profiles.
- [ ] Opinionated "stack generators" for common architectures:
      `make gen-stack-web NAME=myproj` (FastAPI + React + Postgres),
      `make gen-stack-enterprise NAME=myproj` (Spring + Actix auth +
      Axum edge + React + Kafka).

---

## Suggested implementation order

1. **Phase 1** — INTEGRATION_MANIFEST rollout (every AI gen produces
   integration tests).
2. **Phase 2** — project metadata + `dev_skel.project.yml` (unblocks
   Phases 3–6).
3. **Phase 3** — cross-service contracts.
4. **Phase 4** — observability baseline.
5. **Phase 5** — Kubernetes / Helm.
6. **Phase 6** — project-level UX + stack generators.

Each phase is self-contained. Pick one, ship it, move on.
