# Changelog

All notable changes to the Dev Skel project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [2026-04-18] — Phase 5: Kubernetes & Helm

### Added

- **Helm chart templates** at `_skels/_common/helm/` — per-service
  Deployment + Service, Postgres StatefulSet + PVC, Ingress, JWT
  Secret, Namespace, health test hooks. Follows the
  `swarm_digital_twin` patterns (multi-env values, custom image
  registry macros, `_helpers.tpl`).
- **`_bin/skel-deploy` CLI** — `helm-gen` (generate chart from
  `dev_skel.project.yml`), `up` (helm upgrade --install), `down`
  (helm uninstall), `status` (release + pod health).
- **`./kube` wrapper script** in every generated wrapper.
- **Three values profiles**: `values.yaml` (production, Docker Hub
  registry), `values-local.yaml` (minikube/kind, no registry),
  `values-cloud.yaml` (cloud, pull Always, Ingress enabled).
- **K8s-safe naming** — underscores in service slugs auto-converted
  to hyphens for K8s resource names.
- `make deploy-helm-gen WRAPPER=<path>` Makefile target.
- `dev_skel.project.yml` now includes `kubernetes:` (cluster,
  context, namespace) and `images:` (repository) sections.

---

## [2026-04-18] — Phases 1–4 complete

### Phase 1 — AI generation pipeline

- **12 AI manifests** — every skeleton (including go-skel and
  python-fastapi-rag-skel) now ships an AI manifest under
  `_skels/_common/manifests/` with INTEGRATION_MANIFEST for
  cross-service wiring.
- **Prompt hardening** — all 12 skeletons pass
  `make test-ai-generators` with `qwen3-coder:30b`. Java prompts
  enforce JDBC records (not JPA), Rust prompts use inline structs
  (not `crate::models`), React prompts include `category_id` +
  `categories` props, Flutter removed `home_screen.dart` target.
- **Auto-retry** (`--max-retries N`, default 1) — on validation
  failure, the runner cleans up and re-runs the full generation.
- **Multi-phase context** (`{prior_outputs}`) — each target sees
  outputs of all earlier targets for field/import consistency.
- **Structured critique loop** (`--critique`) — after generating each
  file, the model reviews it against the system prompt rules. On
  FAIL, re-generates with the critique reason appended.
- Default model changed from `gemma4:31b` to `qwen3-coder:30b`.

### Phase 2 — Project metadata + orchestration

- **`dev_skel.project.yml`** — auto-generated per-service metadata
  (id, kind, tech, version, port, directory). Regenerated on every
  gen, runs after the AI installer so sidecars are populated.
- **`./services` subcommands** — `list`, `info <slug>`,
  `set-active <slug>` replacing the old bare-listing script.
- **`./run-dev-all` + `./stop-dev-all`** — multi-service launcher
  with combined log tail and PID management.
- **Pagination compatibility** — React `listItems`/`listCategories`
  and Flutter `ItemsClient.listItems` handle both raw arrays and
  paginated wrappers (`{results: [...]}`, `{items: [...]}`).

### Phase 3 — Cross-service contracts

- **Canonical OpenAPI 3.1 spec** at
  `_skels/_common/openapi/wrapper-api.yaml` — 14 operations across
  9 paths, 11 schemas covering auth, categories, items, and state.
- **`_bin/skel-contracts` CLI** — `export` (copy spec to wrapper),
  `validate` (29-check HTTP exercise against a running backend),
  `diff` (breaking-change detection between spec versions), `info`
  (endpoint summary).
- Auto-exported into every generated wrapper at
  `<wrapper>/contracts/openapi/wrapper-api.yaml` via
  `common-wrapper.sh`.

### Phase 4 — Observability baseline

- **`/api/health`** endpoint on all 10 backends (django-bolt was the
  last to gain it).
- **`LOG_FORMAT=console|json`** env var in wrapper `.env`.
- **`OTEL_EXPORTER_OTLP_ENDPOINT`** + `OTEL_SERVICE_NAME` env vars
  in `.env.example` (commented, ready to uncomment).
- **Docker Compose `--profile observability`** — otel-collector +
  Tempo + Grafana in every generated `docker-compose.yml`.
- **Per-service docker-compose entries** — backends with Dockerfiles
  auto-get a container entry. `docker compose up` boots the whole
  stack.

### Infrastructure

- **`./maintenance`** now includes `make test-shared-db-python` as
  step 3/4.

---

## [2026-04-17] — Unified data schema + categories

### Added

- **Categories CRUD** — `/api/categories` with GET, POST, GET/{id},
  PUT/{id}, DELETE/{id} on all 10 backends. Shared (not per-user),
  auth-protected, unique name constraint.
- **`category_id` FK on items** — nullable, ON DELETE SET NULL.
  Items can optionally reference a category.
- **React categories client** — `src/api/categories.ts` +
  `src/hooks/use-categories.ts` + `ItemForm` category dropdown +
  `ItemList` category badge.
- **Flutter categories client** — `lib/api/categories_client.dart` +
  `lib/controllers/categories_controller.dart` + `ItemForm` dropdown.
  Uses `ItemCategory` to avoid collision with Flutter's `Category`.
- **State API in cross-stack test** — 5 state steps
  (save/load/delete/verify/anonymous) added to `exercise_items_api`.
- **Cross-stack test categories exercise** — 5 CRUD steps + 4
  items↔categories FK steps (create with FK, round-trip, delete
  category, verify SET_NULL). Conditional: backends without
  `/api/categories` skip gracefully.

---

## [2026-04-17] — Next.js skeleton + Docker + devcontainers

### Added

- **`next-js-skel`** — js-skel rewritten from plain Node.js to
  Next.js 15 App Router with better-sqlite3 + jose JWT. Ships the
  full wrapper-shared API contract.
- **Dockerfile + `.devcontainer/` for all 12 skeletons** — multi-stage
  builds, per-stack VS Code extensions, Postgres backing service.
- **`make test-react-nextjs`** — cross-stack integration test runner
  for Next.js + React.

---

## [2026-04-16] — AI surfaces + versioning

### Added

- **`./ai upgrade`** — reads sidecar `skeleton_version`, compares to
  skel `VERSION`, extracts CHANGELOG entries, synthesises an AI
  request. Dry-run by default, `--apply` to commit.
- **Wrapper `./ai` fan-out by default** — `./ai "REQUEST"` at project
  root runs against every service. `./ai <slug> "REQUEST"` scopes to
  one.
- **`./backport apply` bumps VERSION + CHANGELOG** — semver patch +
  Keep-a-Changelog entry listing every backported file.
- **`make ci-status` / `ci-watch` / `ci-log`** — GitHub CLI wrapper
  targets for inspecting CI runs.
- **CI fix** — FastAPI `requirements.txt` auto-generated from
  `pyproject.toml` when missing (fixing the `uv pip install` failure
  on CI).
- **Full-stack dialog defaults** — frontend defaults to
  `ts-react-skel`, both halves optional (`--no-backend`,
  `--no-frontend`).

---

## [2026-04-16] — Foundation

### Added

- **12 skeletons** — Python (FastAPI, FastAPI-RAG, Django, Django-Bolt,
  Flask), Java (Spring), Rust (Actix, Axum), Go, Next.js, React/Vite,
  Flutter.
- **Per-service `./ai`** — propose / apply / verify / explain /
  history / undo. In-tree (FAISS RAG) and out-of-tree (stdlib) modes.
- **`./backport`** — service → template diff + apply.
- **Cross-call memory** — JSONL at wrapper + service level.
- **Wrapper-shared environment** — `DATABASE_URL`, `JWT_SECRET`,
  `BACKEND_URL`, `SERVICE_URL_<SLUG>` env vars.
- **Cross-stack integration tests** — 9 React + 2 Flutter backend
  pairs.
- **Skeleton Design Guide** — `_docs/SKELETON-DESIGN-GUIDE.md`.
- **Documentation rewrite** — README.md, all `_docs/*.md` files with
  AI-first framing.
