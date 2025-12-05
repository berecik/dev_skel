# Dev Skel Roadmap

Dev Skel is evolving from “a set of skeletons” into a **multi‑service project platform**:

- You start with a wrapper project and a main backend (Java Spring, FastAPI, or Django).
- Later you add more services into the **same project** – React frontend, Rust Actix auth layer, Rust Axum extra‑fast API, Flutter mobile/desktop app, and more.
- The long‑term goal: these services are **integrated automatically**, share types/contracts, and ship with **turn‑key deployments** (Docker, Compose, Kubernetes, Helm) and **observability**.

This document tracks the roadmap to that vision.

---

## Phase 1 – Strong Multi‑Service Foundation

**Goal:** Formalize the concept of “services inside a wrapper” and expose it via simple tooling.

### 1.1 Project‑Level Service Metadata

- [ ] Introduce a wrapper‑level metadata file (e.g. `dev_skel.project.yml`).
- [ ] Record one entry per service with at least:
  - [ ] `id` – stable identifier (e.g. `backend-1`, `frontend-1`, `auth-actix-1`).
  - [ ] `kind` – `backend`, `frontend`, `worker`, `gateway`, `mobile`, etc.
  - [ ] `tech` – `python-fastapi`, `python-django`, `java-spring`, `ts-react`, `rust-actix`, `rust-axum`, `flutter`, …
  - [ ] `role` – `main-api`, `auth`, `edge-api`, `admin-ui`, `mobile-app`, etc.
  - [ ] `ports` – well‑known dev and internal ports where applicable.
- [ ] Update each `gen` script so generating a service **creates/updates** this metadata file instead of relying purely on directory names.

### 1.2 Wrapper‑Level Service Commands

- [ ] Add wrapper scripts/targets to work with services via metadata:
  - [ ] `./services list` – list all services with id/kind/tech/role.
  - [ ] `./services info <id>` – show details for a single service.
  - [ ] `./services set-active <id>` – mark the “active” service for `./run`, `./test`, etc.
- [ ] Refactor `_skels/_common/common-wrapper.sh` to read service metadata and the active service instead of guessing.

### 1.3 Skeleton Docs & Examples

- [ ] Update skeleton docs (`_docs/*.md`) so each skeleton clearly states:
  - [ ] Typical roles (e.g. FastAPI = main backend, Actix = auth/edge API, Axum = ultra‑fast API, Flutter = mobile/desktop client).
  - [ ] How it is represented in `dev_skel.project.yml`.
  - [ ] Example multi‑service combinations (backend + frontend + auth + extra fast API).

**Outcome:** A wrapper has a **first‑class notion of services**, and tools can introspect and manipulate them.

---

## Phase 2 – Shared Contracts, Types, and API Protocols

**Goal:** Make services share **types and API contracts** from a single source of truth.

### 2.1 Contract Formats and Layout

- [ ] Standardize on OpenAPI for HTTP/REST contracts.
- [ ] Plan for protobuf/gRPC and JSON Schema support where useful.
- [ ] Introduce a project‑level `contracts/` directory:
  - [ ] `contracts/openapi/` for service API specs.
  - [ ] Later: `contracts/proto/`, `contracts/schemas/`, etc.
- [ ] Define conventions, e.g.:
  - [ ] `contracts/openapi/main-api.yaml` – main backend.
  - [ ] `contracts/openapi/auth-api.yaml` – Actix auth service.
  - [ ] `contracts/openapi/mobile-api.yaml` – Axum/mobile‑oriented API.

### 2.2 Contracts in Skeletons

- [ ] For **FastAPI, Django, Spring** skeletons:
  - [ ] Expose OpenAPI specs (FastAPI builtin; plugins or tooling for Django/Spring).
  - [ ] Add `./contracts export` (or similar) to write specs into `contracts/openapi/`.
- [ ] For **Rust Actix/Axum** skeletons:
  - [ ] Integrate OpenAPI generators (`utoipa`/`okapi`‑style or equivalent).
  - [ ] Export specs into the same contracts directory.
- [ ] For **React / Flutter** skeletons:
  - [ ] Document how they **consume** contracts for client codegen.

### 2.3 Type‑Safe Code Generation

- [ ] Create a contract codegen tool (wrapper‑level command, e.g. `./contracts gen`):
  - [ ] From OpenAPI, generate:
    - [ ] Python models/clients (Pydantic/dataclasses).
    - [ ] TypeScript models/clients for `ts-react-skel` / `js-skel`.
    - [ ] Rust models/clients for `rust-actix-skel` / `rust-axum-skel`.
    - [ ] Dart models/clients for Flutter.
  - [ ] Place generated code in framework‑friendly locations (e.g. `backend-1/shared/contracts/`, `frontend-1/src/shared/contracts/`).
- [ ] Integrate codegen into skeleton Makefiles as **optional** steps, so existing generators still work without contracts.

### 2.4 Contract Validation

- [ ] Add `./contracts validate` to:
  - [ ] Validate OpenAPI/JSON Schema.
  - [ ] Optionally detect breaking changes (later with semver rules).

**Outcome:** Multiple services share consistent API contracts and data models, generated from one source of truth.

---

## Phase 3 – Integrated Routing, Ports, and Local Service Discovery

**Goal:** Make multi‑service **local development** plug‑and‑play: predictable ports and routes.

### 3.1 Port & Route Conventions

- [ ] Define default dev ports per role/tech (overridable via config):
  - [ ] Main backend (FastAPI/Django/Spring).
  - [ ] Frontend (React).
  - [ ] Auth service (Actix).
  - [ ] Extra‑fast API (Axum).
- [ ] Store chosen ports in the metadata file and expose them to tooling.

### 3.2 Shared Env Config

- [ ] Generate wrapper‑level `.env.dev` and `.env.test` containing:
  - [ ] `BACKEND_URL`, `AUTH_URL`, `MOBILE_API_URL`, etc.
  - [ ] Stubs for DB, Kafka and other infra endpoints (to be wired in Phase 4).
- [ ] Update skeletons to read these env vars for local dev.

### 3.3 Optional Local Gateway / Reverse Proxy

- [ ] Provide an optional Nginx/Traefik “gateway” skeleton/service that:
  - [ ] Routes `/api` to the main backend.
  - [ ] Routes `/auth` to the Actix auth service.
  - [ ] Routes `/mobile`/`/fast` to the Axum service.
  - [ ] Serves the React/Flutter web bundle at `/`.
- [ ] Generate its configuration from service metadata and port conventions.

### 3.4 Dev‑Mode Orchestration

- [ ] Add wrapper commands for multi‑service dev:
  - [ ] `./run dev-all` – start backend(s), frontend, auth, quick APIs, and minimal infra.
  - [ ] `./stop dev-all` – stop them.
- [ ] Start with simple background processes/`tmux`/`foreman` before relying fully on Docker.

**Outcome:** A Dev Skel project with several services runs locally with sensible defaults and consistent URLs.

---

## Phase 4 – Automatic Local Deployment with Docker & Docker Compose

**Goal:** One command to run **all services + infra** via containers on a developer machine.

### 4.1 Docker Baseline per Skeleton

- [ ] Ensure each skeleton ships with an up‑to‑date, production‑leaning Dockerfile:
  - [ ] FastAPI: multi‑stage with uvicorn/gunicorn.
  - [ ] Django: multi‑stage with gunicorn and static assets.
  - [ ] Java Spring: JAR build + runtime stage.
  - [ ] Actix/Axum: release binary in minimal or distroless base.
  - [ ] React: build + static server or proxy.
  - [ ] Flutter: strategy for web or containerized desktop builds where feasible.

### 4.2 Compose File Generation

- [ ] Implement `./deploy compose-gen` (or `make compose-gen`) that:
  - [ ] Reads service metadata.
  - [ ] Generates `docker-compose.yml` including:
    - [ ] One container per service.
    - [ ] Ports, env, dependencies based on metadata.
    - [ ] Infra services:
      - [ ] Database (PostgreSQL or configurable).
      - [ ] HTTP reverse proxy (if enabled).
      - [ ] Kafka (or compatible broker).
      - [ ] Monitoring stack (Prometheus + Grafana).
  - [ ] Support overrides via `docker-compose.override.dev.yml`.

### 4.3 Wrapper Deployment Commands (Local)

- [ ] Add wrapper commands:
  - [ ] `./deploy up` – `docker compose up -d` for all services + infra.
  - [ ] `./deploy down` – `docker compose down` (with optional volume cleanup).
  - [ ] `./deploy logs [service]` – follow container logs.
- [ ] Make existing scripts (`./run docker`, `./stop`) aware of or reuse these commands.

**Outcome:** Any multi‑service project can be lifted into Docker/Compose with a single command.

---

## Phase 5 – Kubernetes & Helm Integration

**Goal:** Generate Kubernetes/Helm configs to run the same project on clusters.

### 5.1 K8s/Helm Structure

- [ ] Decide on a deployment layout, e.g. under `deploy/`:
  - [ ] `deploy/helm/` – umbrella chart for the whole project.
  - [ ] `deploy/helm/services/<service-id>/` – per‑service subcharts.
  - [ ] `deploy/helm/infra/` – DB, proxy, Kafka, monitoring subcharts.

### 5.2 Helm Template Generation

- [ ] Implement `./deploy helm-gen` to:
  - [ ] Use service metadata (id, tech, role, ports, resources, env).
  - [ ] Generate Deployments/StatefulSets, Services, Ingress, ConfigMaps and Secrets stubs.
  - [ ] Include default HPAs with sane initial values.
- [ ] Allow configuration via `values.yaml` (committed) and `values.local.yaml` (gitignored for developers).

### 5.3 CI‑Friendly Build & Deploy

- [ ] Add CI‑oriented Make targets:
  - [ ] `make ci-build-images` – build all service images with project/commit‑based tags.
  - [ ] `make ci-push-images` – push to a registry.
  - [ ] `make ci-deploy` – run `helm upgrade --install` using generated charts.
- [ ] Ship a reference GitHub Actions workflow using these targets.

### 5.4 Environment Profiles

- [ ] Introduce environment profiles (`dev`, `staging`, `prod`) controlling:
  - [ ] Replica counts and resource limits.
  - [ ] Ingress hosts and TLS.
  - [ ] Feature flags and optional services (e.g. Kafka in dev vs prod).

**Outcome:** A Dev Skel project can be deployed to Kubernetes via generated Helm charts with minimal manual YAML work.

---

## Phase 6 – Built‑In Observability & Diagnostics

**Goal:** Each skeleton becomes an **observable service** by default, with cross‑service insights.

### 6.1 Observability Baseline per Skeleton

- [ ] Add standard observability wiring to skeletons:
  - [ ] Structured JSON logging with correlation IDs.
  - [ ] HTTP and DB metrics (Prometheus style).
  - [ ] OpenTelemetry tracing with OTLP exporters.
- [ ] Standardize env vars like:
  - [ ] `SERVICE_NAME`, `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`.

### 6.2 Trace Propagation

- [ ] Ensure HTTP clients and middleware in:
  - [ ] FastAPI, Django, Spring.
  - [ ] Actix, Axum.
  - [ ] React/Node.js, Flutter (where applicable).
  - [ ] propagate `traceparent` and related headers between services.

### 6.3 Monitoring Stack Integration

- [ ] Extend Compose and Helm templates to:
  - [ ] Add Prometheus scrape configs for all services.
  - [ ] Provide Grafana dashboards for common stacks:
    - [ ] FastAPI + React.
    - [ ] Django + React.
    - [ ] Spring + Rust APIs.
- [ ] Add a helper `./observability dashboards` to import or generate dashboards.

### 6.4 Health & Diagnostics

- [ ] Standardize `/health` and `/ready` endpoints for all HTTP services.
- [ ] Add simple diagnostics pages/endpoints for DB, Kafka, and external dependencies.

**Outcome:** Generated stacks are observable and diagnosable from day one.

---

## Phase 7 – Project‑Level Orchestration & Developer UX

**Goal:** Treat the wrapper as a **single product** even though it contains many services.

### 7.1 Unified Project Commands

- [ ] Implement project‑level commands that fan out across services:
  - [ ] `./project test` – run tests for all services, aggregate status.
  - [ ] `./project lint` – run linters/formatters everywhere.
  - [ ] `./project build` – build all artifacts/images.
- [ ] Use service metadata to discover the right scripts in each service directory.

### 7.2 Service Graph & Dependencies

- [ ] Record service dependencies (could reuse metadata or add `services.graph.yml`):
  - [ ] Example: `frontend-1` depends_on `backend-1`; `backend-1` depends_on `db` and `kafka`.
- [ ] Add `./project graph` to:
  - [ ] Emit a DOT/PlantUML/mermaid diagram, or
  - [ ] Print a readable dependency tree.

### 7.3 Environment Management UX

- [ ] Provide simple helpers, e.g. `./env use dev|staging|prod`, to:
  - [ ] Switch active environment profile.
  - [ ] Influence which Compose files / Helm values / env files are used.

### 7.4 Opinionated Example Stacks

- [ ] Ship high‑level “stack generators” for common architectures:
  - [ ] **Web App Stack** – Django or FastAPI + React + Postgres + proxy + monitoring.
  - [ ] **Auth + Edge APIs Stack** – Spring main backend + Actix auth + Axum mobile API + Kafka.
- [ ] Expose them as Make targets, e.g.:
  - [ ] `make gen-stack-web NAME=myproj`.
  - [ ] `make gen-stack-auth-edge NAME=myproj`.

**Outcome:** From the developer’s point of view, a Dev Skel project is one orchestrated system with great ergonomics.

---

## Suggested Implementation Order

To reduce risk and deliver value incrementally:

1. Phase 1 – Metadata + service commands.
2. Phase 3 (core parts) – Ports and env wiring.
3. Phase 2 – Contracts and type sharing.
4. Phase 4 – Docker/Compose stack.
5. Phase 6 (baseline) – Logging/metrics/health.
6. Phase 5 – Kubernetes/Helm.
7. Phase 6 (advanced) – Tracing and dashboards.
8. Phase 7 – Orchestration UX and example stacks.

This roadmap should remain high‑level: individual issues/PRs can reference concrete checklist items from here.
