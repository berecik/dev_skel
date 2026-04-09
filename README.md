# Dev Skel – Multi‑Service Project Skeleton Generator

Dev Skel is a collection of opinionated project skeletons that makes it easy to create **multi‑service projects** that share a common database, JWT authentication, and a single environment file.

You start by generating a wrapper project with a backend (Django, Django‑Bolt, FastAPI, Flask, Java Spring, etc.) and giving it a **service name** — that name becomes the directory the service lives in. Later you can add more services into the **same project** – for example a React frontend, a Rust Actix service, or another Python backend – and they all share the wrapper‑level `.env`, the shared SQLite/Postgres database, and a single JWT secret so a token issued by one service is accepted by every other service in the project.

Each skeleton ships with best‑practice defaults (tests, linting, Docker build, dev tooling). The `_bin/skel-gen` tool (Ollama‑backed AI by default; `--static` for an AI-free baseline) and the main `Makefile` orchestrate how these services are created and wired into a single project directory.

## Core Ideas

- **One project, many services**: A project directory is a **wrapper** that can host multiple backend, frontend, and worker services. Each service lives in its own subdirectory inside the wrapper.
- **Directory = service name**: When you generate a service you give it a **display name** (e.g. `"Ticket Service"`). The on‑disk directory becomes its slug (e.g. `myproj/ticket_service/`). If the slug already exists in the wrapper, a numeric suffix is appended.
- **Shared environment** at the wrapper level (`<wrapper>/.env`):
  - `DATABASE_URL` — every backend service points at the same database (default: a shared SQLite file at `<wrapper>/_shared/db.sqlite3`; swap to `postgresql://...` for production).
  - `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL` — every backend service signs and verifies tokens with the same secret, so a token issued by one service is accepted by every other service.
  - `BACKEND_URL` — the URL the **frontend(s)** in the wrapper call by default. The React skeleton's `src/api/items.ts` and `src/state/state-api.ts` compose endpoints as `${BACKEND_URL}/api/items` and `${BACKEND_URL}/api/state`. Defaults to `http://localhost:8000` (the django-bolt convention); point it at any other backend by editing the value or by referencing one of the auto-generated `SERVICE_URL_<SLUG>` values from `_shared/service-urls.env`.
- **Multi‑service dispatch**: The wrapper ships `./services`, `./run`, `./test`, `./build`, `./stop`, `./install-deps` — every script discovers services dynamically, sources `<wrapper>/.env` first, and accepts an optional first arg matching a service slug to dispatch to that service only. Without the arg, "fan‑out" scripts (`./test`, `./install-deps`, `./build`, `./stop`) operate on every service in the wrapper, while "single‑shot" scripts (`./run`) target the first one.
- **Composable skeletons**: Mix and match — e.g. a Django‑Bolt API backend, a FastAPI worker, and a React frontend in one wrapper.
- **Safe re‑generation**: Re‑running a skeleton against an existing wrapper **adds a new service** without overwriting `.env`, `_shared/`, or any existing service directory.

## Generated Wrapper Layout

```text
myproj/
├── .env                    # SHARED env: DATABASE_URL, JWT_SECRET, ...
├── .env.example            # template (committed; .env is gitignored)
├── docker-compose.yml      # Postgres backing service (opt-in)
├── _shared/
│   ├── README.md           # explains the shared layer
│   ├── db.sqlite3          # default shared SQLite database
│   ├── postgres-data/      # bind-mount target for the compose service
│   └── service-urls.env    # auto-generated SERVICE_URL_<SLUG> per service
├── README.md / Makefile    # wrapper docs + Makefile delegating to ./scripts
├── services                # discovery script — lists every service
├── run / test / build / stop / install-deps
│                           # multi-service dispatch wrappers (see below)
├── ticket_service/         # first backend (django-bolt)
├── auth_api/               # second backend (fastapi)
└── web_ui/                 # frontend (ts-react)
```

### Cross-service URLs (`_shared/service-urls.env`)

Every time `common-wrapper.sh` runs (via any `gen-*` invocation) it
regenerates `_shared/service-urls.env` with one
`SERVICE_URL_<UPPER_SLUG>=http://...` entry per service in the wrapper.
Ports are allocated sequentially from `SERVICE_PORT_BASE` (default
`8000`), in alphabetical slug order, and **previously assigned ports are
preserved** so adding a new service doesn't shuffle existing URLs:

```ini
SERVICE_URL_AUTH_API=http://127.0.0.1:8001
SERVICE_PORT_AUTH_API=8001
SERVICE_URL_TICKET_SERVICE=http://127.0.0.1:8000
SERVICE_PORT_TICKET_SERVICE=8000
```

Every wrapper script (`./run`, `./test`, ...) sources this file alongside
`.env`, so handlers can call sibling services via
`os.environ['SERVICE_URL_AUTH_API']` (Python),
`process.env.SERVICE_URL_AUTH_API` (Node), `${SERVICE_URL_AUTH_API}`
(Spring `application.properties`), or `std::env::var("SERVICE_URL_AUTH_API")`
(Rust). Override the host with `SERVICE_HOST=...` or the starting port
with `SERVICE_PORT_BASE=...` in `.env` and re-run any wrapper script.

### Postgres via Docker Compose

The wrapper ships an opt-in `docker-compose.yml` that brings up a single
Postgres container against the same `DATABASE_*` variables that live in
`.env`:

```bash
docker compose up postgres -d   # start the shared Postgres
# Edit .env to point at it (one-line change for every backend):
sed -i '' 's|^DATABASE_URL=.*|DATABASE_URL=postgresql://devskel:devskel@localhost:5432/devskel|' .env
sed -i '' 's|^DATABASE_JDBC_URL=.*|DATABASE_JDBC_URL=jdbc:postgresql://localhost:5432/devskel|' .env
sed -i '' 's|^SPRING_DATASOURCE_URL=.*|SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/devskel|' .env

./install-deps                  # reinstall every service against Postgres
./test                          # rerun every service's tests against Postgres
```

The compose file persists Postgres state in `_shared/postgres-data/` so
the shared database survives container restarts. A commented-out
`ticket_service:` example shows how to add per-service container entries
when you want to dockerize the whole stack.

### Wrapper scripts

Every wrapper script sources `<wrapper>/.env` so child processes inherit the
shared `DATABASE_URL`, `JWT_SECRET`, and friends. Each script accepts an
optional first argument matching a service slug to dispatch to that
service only:

```bash
./services                  # list every service in the wrapper
./run                       # run the first service in the wrapper
./run ticket_service dev    # run a specific service in dev mode
./test                      # run tests for every service that has ./test
./test ticket_service       # only run that service's tests
./install-deps              # install deps for every service
./stop                      # stop every running service
```

Forwarded arguments after the optional slug go straight to the inner
script, so `./run ticket_service dev --port=8001` works exactly as you
would expect.

### Shared environment

`<wrapper>/.env` is the single source of truth for cross-service config.
**Every backend skeleton — Python (FastAPI / Django / Django‑Bolt /
Flask), Java (Spring Boot), Rust (Actix / Axum), and Node — reads these
variables on startup**, so a token minted by one service is accepted by
every other service and they all point at the same database.

The default contents (also documented in `<wrapper>/.env.example`):

```ini
# Database — every backend service points at the same store.
# DATABASE_URL is the abstract / Python form; DATABASE_JDBC_URL and
# SPRING_DATASOURCE_URL are JVM-friendly variants. Keep them in sync
# when you change the value.
DATABASE_URL=sqlite:///_shared/db.sqlite3
DATABASE_JDBC_URL=jdbc:sqlite:_shared/db.sqlite3
SPRING_DATASOURCE_URL=jdbc:sqlite:_shared/db.sqlite3

# JWT — same secret for every service so a token issued by one is
# accepted by every other service in the wrapper.
JWT_SECRET=change-me-32-bytes-of-random-data
JWT_ALGORITHM=HS256
JWT_ISSUER=devskel
JWT_ACCESS_TTL=3600
JWT_REFRESH_TTL=604800

# Default backend URL — frontends in this wrapper read this to know
# which backend they should call. Defaults to the django-bolt
# convention (`http://localhost:8000`); the React skeleton's
# `src/api/items.ts` and `src/state/state-api.ts` compose endpoints
# as `${BACKEND_URL}/api/items` and `${BACKEND_URL}/api/state`.
BACKEND_URL=http://localhost:8000
```

Per-language entry points:

| Stack | Where the env is read |
|-------|----------------------|
| Django / Django‑Bolt | `myproject/settings.py` (or `app/settings.py`) — `_build_databases()` + `JWT_*` |
| FastAPI | `core/config.py` — `_resolve_database_url()` + `JWT_*` |
| Flask | `app/config.py` — `Config` class |
| Spring Boot | `application.properties` (`${SPRING_DATASOURCE_URL}`, `${JWT_SECRET}`) → `JwtProperties` bean |
| Rust Actix / Axum | `src/config.rs::Config::from_env()` + `load_dotenv()` |
| Node | `src/config.js` — `dotenv` loads wrapper `.env` then local |
| React (Vite) | `vite.config.ts` (env-loader plugin) → `src/config.ts` — exposes `config.backendUrl`, `config.jwt.*` (frontend never sees `JWT_SECRET`) |

To switch the entire wrapper from the default shared SQLite to Postgres,
edit the wrapper `.env` and update **all three** database URL variants in
lockstep:

```ini
DATABASE_URL=postgresql://user:pass@localhost:5432/myproj
DATABASE_JDBC_URL=jdbc:postgresql://localhost:5432/myproj
SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/myproj
DATABASE_USER=user
DATABASE_PASSWORD=pass
```

Every backend service picks up the change on the next restart — no
per-service config edits needed.

## Current Capabilities

Today Dev Skel focuses on these building blocks:

### Backends (Python)

- **FastAPI** (`python-fastapi-skel`) – async web API with a DDD‑style layout and automatic OpenAPI docs.
- **Django** (`python-django-skel`) – classic Django backend with batteries included.
- **Django‑Bolt** (`python-django-bolt-skel`) – Django + Rust HTTP layer (`django-bolt`, ~60k RPS) with `msgspec.Struct` schemas, JWT/OAuth helpers, and async ORM endpoints. Mirrors the layout of [`claude_on_django`](https://github.com/beret/claude_on_django). Ships the wrapper-shared **`/api/items`** CRUD resource and **`/api/state`** save/load endpoints out of the box, so the React skeleton's example UI works against it without any extra wiring. This is the **default backend** the React skeleton points at via `BACKEND_URL`.
- **Flask** (`python-flask-skel`) – lightweight WSGI backend.

### Frontends (TypeScript/JavaScript)

- **React + Vite + TypeScript** (`ts-react-skel`) – React 19 SPA frontend with Vitest, ESLint, Prettier. Ships a working full-stack example against the wrapper-shared `BACKEND_URL` (defaults to django-bolt at `http://localhost:8000`):
  - Typed item repository (`src/api/items.ts`) hitting `${BACKEND_URL}/api/items`.
  - JWT auth layer (`src/auth/token-store.ts` + `src/auth/use-auth-token.ts`).
  - `useItems` custom hook (`src/hooks/use-items.ts`) with optimistic create + abort handling.
  - `LoginForm` / `ItemForm` / `ItemList` components.
  - **React state management layer** (`src/state/`) — pub/sub store + `useAppState<T>(key, default)` hook + `<AppStateProvider>` that hydrates from `${BACKEND_URL}/api/state` on login. UI slices (filters, sort order, preferences) persist across reloads via the backend.
- **Node.js backend / tools** (`js-skel`) – plain Node.js projects.

### Other backends

- **Java Spring Boot** (`java-spring-skel`) – production‑grade JVM backend.

### Rust quick APIs / services

- **Actix‑web** (`rust-actix-skel`) – fast Rust HTTP services (ideal for quick APIs or edge services).
- **Axum** (`rust-axum-skel`) – ergonomic Rust web framework on top of Tokio.

You can generate any combination of these in a single project wrapper. The recommended starting points right now are:

- `python-fastapi-skel` or `python-django-skel` for the main backend.
- `ts-react-skel` for the main frontend.
- `rust-actix-skel` for additional quick APIs.

## Quick Start – Installation

### Install System Dependencies

Install required system dependencies for all skeletons or specific frameworks:

```bash
# List all available skeletons and their dependency status
./skel-deps --list

# Install dependencies for all frameworks
./skel-deps --all

# Install dependencies for a specific framework
./skel-deps java-spring-skel
./skel-deps python-django
./skel-deps rust-actix
```

Supported systems: macOS (Homebrew), Ubuntu/Debian (apt), Arch Linux (pacman), Fedora/RHEL (dnf)

See [DEPENDENCIES.md](_docs/DEPENDENCIES.md) for detailed information.

### Install or Update Dev Skel Locally

Use the provided helper scripts in `_bin/`:

```bash
# First-time install to your development directory (default: "$HOME/dev_skel")
_bin/install-dev-skel

# Later, to pull updates from this repo into your local installation
_bin/update-dev-skel

# If you keep this repo and your installed copy in sync manually
_bin/sync-dev-skel
```

## Generate Multi‑Service Projects

There are two equivalent ways to generate services:

1. From the repo root via the main `Makefile` targets.
2. From anywhere using the relocatable `_bin/skel-gen` tool.

### 1) From the repo root via Makefile targets

```bash
# First backend service in a new wrapper (FastAPI) — defaults to "backend/"
make gen-fastapi NAME=myproj

# First backend service in a new wrapper (Django)
make gen-django NAME=myproj

# First backend service in a new wrapper (Django-Bolt — Rust-powered Django)
make gen-django-bolt NAME=myproj

# Pass SERVICE=… to the Makefile target to control the service display name
# (slugified to the on-disk directory)
make gen-django-bolt NAME=myproj SERVICE="Ticket Service"   # → myproj/ticket_service/
make gen-fastapi   NAME=myproj SERVICE="Auth API"           # → myproj/auth_api/
make gen-react     NAME=myproj SERVICE="Web UI"             # → myproj/web_ui/
```

### 2) Using `_bin/skel-gen` from anywhere — **AI by default**

As of 2026-04, `_bin/skel-gen` is a thin dispatcher that **defaults to
AI-augmented generation** via `_bin/skel-gen-ai`. The previous static-only
behavior is still available via `_bin/skel-gen-static` (or by passing
`--static` to `skel-gen`).

```bash
# Fully interactive AI mode (full-stack dialog: picks backend +
# frontend, asks for item / auth / three custom prompts, generates
# both halves, runs the integration phase + test-and-fix loop)
_bin/skel-gen                            # cwd as wrapper
_bin/skel-gen myproj                     # fresh wrapper directory

# Single-skel AI mode (legacy positional layout still works)
_bin/skel-gen myproj python-django-bolt-skel "Tickets API"

# Static fallback — no Ollama, no AI overlays. Use this when you
# want a deterministic AI-free baseline or you don't have a model
# available locally.
_bin/skel-gen --static . python-fastapi-skel                # → $PWD/backend/
_bin/skel-gen --static myproj python-django-bolt-skel "Ticket Service"
_bin/skel-gen-static myproj python-fastapi-skel "Auth API"  # equivalent
```

Three CLI entrypoints, all positional `[proj_name] [skel_name] [service_name]`:

- **`_bin/skel-gen`** — canonical entrypoint (NEW: AI by default).
  Dispatches to `skel-gen-ai` unless `--static` is passed.
- **`_bin/skel-gen-static`** — explicit static fallback. Same behavior
  as the pre-2026-04 `_bin/skel-gen`. No Ollama needed.
- **`_bin/skel-gen-ai`** — explicit AI invocation. Same as `skel-gen`
  without `--static`. Kept as a stable name for scripts that want to
  pin the AI path explicitly.

Parameters (all positional, all optional):

- `proj_name` – **leaf** wrapper directory name (no `/`), created under the current working directory. Pass `.` (or omit) to install into the current directory itself; the project's display name then comes from the cwd basename.
- `skel_name` – skeleton directory name under `_skels/` (for example `python-fastapi-skel`, `ts-react-skel`). When omitted in static mode, an interactive picker lists every available skeleton; when omitted in AI mode, the **full-stack dialog** runs (backend + frontend + service / item / auth / three custom prompts).
- `service_name` – optional **service display name** (e.g. `"Ticket Service"`). The on‑disk subdirectory becomes its slug (`ticket_service`). If omitted, the per‑skeleton default base is used: `backend` for Python backends, `frontend` for React, `service` for Rust/Java/Node.

Dev Skel ensures the service directory name is unique within the wrapper. Generating two services with the same name appends a numeric suffix (`ticket_service-1`, `ticket_service-2`, ...).

If you accidentally pass a skeleton name in the project slot
(`_bin/skel-gen python-fastapi-skel`) both dispatchers detect it and
print an actionable error suggesting `_bin/skel-gen . python-fastapi-skel`
instead.

### 3) AI-augmented generation with Ollama (`_bin/skel-gen-ai`)

`_bin/skel-gen-ai` is the explicit AI invocation that `_bin/skel-gen`
exec's by default (as of 2026-04). It runs the same wrapper-aware
skeleton generation, then asks Ollama to **rewrite a curated set of
"core" service files** (models, schemas, routes, services, tests)
based on the choices you make in an interactive dialog. Use the
`_bin/skel-gen-ai` name in scripts that want to pin the AI path
explicitly; use `_bin/skel-gen` for the canonical entrypoint that
follows whichever default the project ships.

#### Two modes

* **Full-stack mode** (default when `skel_name` is omitted): the dialog
  asks for a backend skeleton AND a frontend skeleton (the frontend can
  be skipped), one project name, two service display names, the
  canonical item entity, an auth style, and **three custom freeform
  prompts** — one each for the backend, frontend, and integration
  phases. The driver then generates the backend per-target overlay,
  the frontend per-target overlay, runs the backend's
  `INTEGRATION_MANIFEST` (now with both services on disk so the
  frontend appears as a sibling), and finally runs the test-and-fix
  loop. The wrapper-shared `/api/items` + `/api/auth/login` contract
  is enforced by default for backends that ship it (currently
  `python-django-bolt-skel` and `python-fastapi-skel`); the React
  frontend's `src/api/items.ts` client works against either out of the
  box.
* **Single-skeleton mode** (legacy): when an explicit positional
  `skel_name` is given, only that one skeleton is generated. Same
  behavior as pre-2026-04 `skel-gen-ai` invocations — kept for
  scripted users.

```bash
# Fully interactive full-stack flow (cwd as wrapper, dialog asks for
# backend + frontend + service / item / auth + three custom prompts)
_bin/skel-gen-ai

# Same but in a fresh wrapper directory
_bin/skel-gen-ai myproj

# Fully scripted full-stack run (skip the dialog by pre-filling flags)
_bin/skel-gen-ai myproj \
    --backend python-django-bolt-skel \
    --frontend ts-react-skel \
    --backend-service-name "Items API" \
    --frontend-service-name "Web UI" \
    --item-name ticket \
    --auth-type jwt \
    --backend-extra "use refresh tokens with 2 hour TTL" \
    --frontend-extra "use Tailwind CSS for styling" \
    --integration-extra "add a smoke test that hits /api/items via fetch" \
    --ollama-model gemma4:31b

# Backend-only project (skip the frontend pick)
_bin/skel-gen-ai myproj --no-frontend --backend python-fastapi-skel

# Single-skel mode (legacy — pass an explicit positional skel_name)
_bin/skel-gen-ai myproj python-django-skel

# Dry run — show what would be generated, no Ollama calls
_bin/skel-gen-ai myproj --no-input --dry-run
```

The full-stack dialog walks the user through six logical steps:

| Step | Question | Default | Notes |
|------|----------|---------|-------|
| 1 | Pick a backend | first backend that ships `/api/items` (currently `python-django-bolt-skel`) | All AI-supported backends listed; the items-contract badge marks the ones the React frontend can talk to out of the box |
| 2 | Pick a frontend | `ts-react-skel` | Pick `0` / `none` to skip — useful for backend-only projects |
| 3 | Service display names | `Items API` + `Web UI` | Slugified to `items_api/` and `web_ui/` directories |
| 4 | Main CRUD entity | `item` | Becomes the `{item_class}` (PascalCase) and `{items_plural}` (snake_case plural) used by every per-skel manifest |
| 5 | Auth type | `jwt` | none / basic / session / jwt / oauth / api_key |
| 6 | Three custom prompts | (blank) | `backend_extra`, `frontend_extra`, `integration_extra` — each is plumbed into the matching phase via the `{backend_extra}` / `{frontend_extra}` / `{integration_extra}` placeholders so manifest authors can pull them into their prompts |

The dialog prints a summary line about the items contract before
proceeding so you know whether the React frontend will get a working
items round-trip out of the box (django-bolt + fastapi → yes; django,
flask, java-spring, rust, js → not yet, the React `src/api/items.ts`
will receive 404 until you wire a matching backend route).

When generating a project from outside an interactive shell (CI,
scripts), pass every choice explicitly via the `--backend`,
`--frontend`, `--backend-service-name`, `--frontend-service-name`,
`--item-name`, `--auth-type`, `--backend-extra`, `--frontend-extra`,
`--integration-extra` flags + `--no-input`. The dialog steps then
run silently using the supplied values.

**Backwards compat**: the older `--auth-details` flag is still
accepted as an alias for `--backend-extra`.

**Requirements**: Ollama running locally with the chosen model pulled.

```bash
ollama serve                              # in another terminal
ollama pull gemma4:31b                    # one-time (~19 GB download)
_bin/skel-gen-ai myproj python-django-skel
```

Defaults: `OLLAMA_BASE_URL=http://localhost:11434`,
`OLLAMA_MODEL=gemma4:31b`. Override with environment variables or
the `--ollama-url` / `--ollama-model` flags. The default `OLLAMA_TIMEOUT`
is `600` seconds — sized for a ~30B-class instruction model running
locally. Drop to a smaller model (e.g. `qwen3-coder:30b` or
`qwen2.5-coder:7b`) on slower hardware:

```bash
OLLAMA_MODEL=qwen3-coder:30b OLLAMA_TIMEOUT=300 make test-ai-generators
```

**All 9 skeletons are AI-supported**: `python-django-skel`,
`python-django-bolt-skel`, `python-fastapi-skel`, `python-flask-skel`,
`java-spring-skel`, `rust-actix-skel`, `rust-axum-skel`, `js-skel`,
`ts-react-skel`. The Python and JVM backends ask Ollama to rewrite the
canonical CRUD layer (model + repository + service + controller +
tests) for the user's `{item_class}`; the Rust skels add new
`models.rs` + `handlers.rs` modules and re-wire `main.rs`; the Node
skel adds a `node:sqlite`-backed CRUD module + tests; the React skel
adds a typed fetch client + `<{item_class}List>` / `<{item_class}Form>`
components and updates `App.tsx` to mount them.

To add another skeleton, drop a manifest at
`_skels/_common/manifests/<skel-name>.py` listing the files Ollama
should generate (see the existing manifests for the format). The shared
library lives in `_bin/skel_ai_lib.py`. The picker (`_bin/skel-gen-ai`
with no arguments) auto-discovers manifests under
`_skels/_common/manifests/`.

#### Integration phase (second Ollama session)

After the per-target manifest finishes generating the new service,
`skel-gen-ai` runs a **second Ollama session** that wires the freshly
generated service into the rest of the wrapper. This phase is opt-in
per skeleton: it activates when the per-skel manifest declares an
`INTEGRATION_MANIFEST = {...}` block alongside the existing `MANIFEST`.

What the integration session does:

1. **Discovers sibling services** in the wrapper by walking
   `<wrapper>/<service>/` and reading a few key files from each (the
   marker files for django, django-bolt, fastapi, flask, java-spring,
   rust-actix, rust-axum, js, and ts-react are baked into
   `_bin/skel_ai_lib._SIBLING_KEY_FILES`). Each sibling's slug, kind,
   tech, and key-file excerpts get exposed to the integration prompt
   via the `{wrapper_snapshot}`, `{sibling_count}`, and `{sibling_slugs}`
   placeholders.
2. **Renders + writes additive integration files** — typed sibling
   clients, integration tests, and any other glue the manifest asks
   for. These files are *new*, never overwriting the per-target
   manifest's outputs.
3. **Runs a test-and-fix loop**: executes the manifest's `test_command`
   (defaults to `./test`) inside the new service. If the tests fail,
   asks Ollama to repair each integration file in turn (one round-trip
   per file), then re-runs. The loop is bounded by `fix_iterations`
   (default `2`).

```bash
# Default behavior: run both phases (per-target + integration + test loop)
_bin/skel-gen-ai myproj python-django-bolt-skel "Tickets API"

# Only run the per-target generation; skip the integration phase
_bin/skel-gen-ai myproj python-django-bolt-skel "Tickets API" --no-integrate

# Run the integration phase but skip the test-and-fix loop (useful in
# CI or when you want to inspect the generated tests before running)
_bin/skel-gen-ai myproj python-django-bolt-skel "Tickets API" --no-test-fix
```

Currently `python-django-bolt-skel` is the canonical example with a
complete `INTEGRATION_MANIFEST` (sibling clients + integration tests).
The other skeletons load fine without one — the integration phase is
silently skipped when no `INTEGRATION_MANIFEST` is declared. To add it
to a new skeleton, copy the structure from
`_skels/_common/manifests/python-django-bolt-skel.py` and edit the
prompts to match your stack.

**End-to-end AI testing**: `_bin/test-ai-generators` runs the entire AI
pipeline (base scaffold + Ollama overlay + per-skeleton sanity check —
`manage.py check` for Django, module import for FastAPI, plus a syntax
check on every generated file) for every skeleton that has a manifest
(`python-django-skel`, `python-django-bolt-skel`, `python-fastapi-skel`,
`python-flask-skel`). It is intentionally **not** part of
`make test-generators` because it needs a running Ollama daemon and can
take 30+ minutes total.

```bash
# All AI-supported skeletons (auto-discovered from manifests)
make test-ai-generators

# One skeleton at a time
make test-gen-ai-django
make test-gen-ai-django-bolt
make test-gen-ai-fastapi

# Dry run — verify dispatch + base scaffold without calling Ollama
make test-ai-generators-dry

# Custom item / auth, keep the result for inspection
_bin/test-ai-generators \
    --skel python-django-bolt-skel \
    --service-name "Ticket Service" \
    --item-name ticket --auth-type jwt \
    --keep
```

Each run lands under `_test_projects/test-ai-<skel>/` and is cleaned up
on success unless you pass `--keep`. If Ollama is not reachable the runner
prints a friendly skip message and exits with status 2 instead of failing
hard.

### React + FastAPI cross-stack integration test (`_bin/test-react-fastapi-integration`)

Same shape as the django-bolt test below but exercises the
`python-fastapi-skel` + `ts-react-skel` pair instead. Generates a
wrapper containing both skeletons, rewrites `BACKEND_URL` to a
non-conflicting port, builds React, starts FastAPI via uvicorn, and
runs the canonical 9-step register → login → CRUD → complete → reject
flow over real HTTP.

```bash
make test-react-fastapi          # full run (~1 minute on a warm cache)
make test-react-fastapi-keep     # leave _test_projects/test-react-fastapi on disk
_bin/test-react-fastapi-integration --port 19877
```

The fastapi skel ships a wrapper-shared API layer at
`app/wrapper_api/` (added in 2026-04) so the React skel's
`src/api/items.ts` and `src/state/state-api.ts` clients work against
either FastAPI or django-bolt without code changes. The wrapper-shared
layer auto-creates its tables (`wrapper_user`, `items`, `react_state`)
on import, so no migrations step is required before the server boots.

### React + django-bolt cross-stack integration test (`_bin/test-react-django-bolt-integration`)

`_bin/test-react-django-bolt-integration` is the end-to-end proof
that the canonical full-stack pair (`python-django-bolt-skel` +
`ts-react-skel`) works through real HTTP. It:

1. Generates a wrapper containing both skeletons.
2. Rewrites `BACKEND_URL` in `<wrapper>/.env` to a non-conflicting
   port (default `18765`).
3. Re-builds the React frontend so the Vite plugin bakes the new
   `BACKEND_URL` into the bundle, then verifies the bundle contains
   the expected URL, `/api/items`, `/api/auth/login`, `Bearer`, and
   the `devskel` JWT issuer.
4. Runs `manage.py makemigrations app` + `manage.py migrate` against
   the django-bolt service's per-service `.venv`.
5. Starts the django-bolt server in the background on the chosen port
   and waits for it to become reachable.
6. Exercises the cross-stack items API flow over real HTTP using the
   same shape the React `src/api/items.ts` client uses:
   - `POST /api/auth/register` → 201
   - `POST /api/auth/login` → 200 + JWT
   - `GET /api/items` (initial state)
   - `POST /api/items` → 201 + new id
   - `GET /api/items` (verify new item is in the list)
   - `GET /api/items/<id>` (round-trip retrieve)
   - `POST /api/items/<id>/complete` (verify the @action endpoint)
   - `GET /api/items` without token (verify JWT enforcement → 401)
   - `GET /api/items` with invalid token (verify JWT validation → 401)
7. Stops the server cleanly (SIGTERM, then SIGKILL on timeout) and
   removes the wrapper unless the test failed or `--keep` was passed.

```bash
make test-react-django-bolt          # full run (~3 minutes on a cold cache)
make test-react-django-bolt-keep     # leave _test_projects/test-react-django-bolt on disk
_bin/test-react-django-bolt-integration --port 19876   # custom port
_bin/test-react-django-bolt-integration --no-skip       # fail on missing Node
```

Skips gracefully (exit `2`) when Node/npm is not installed. Failing
runs leave the wrapper on disk under `_test_projects/test-react-django-bolt/`
so you can poke at the React build artifacts (`web_ui/dist/assets/`)
and the django-bolt server log (`items_api/test-server.log`).

### Shared-DB integration test (`_bin/test-shared-db`)

`_bin/test-shared-db` is the cross-language proof that every backend
skeleton wired to the wrapper-shared environment actually reads from the
same database. It:

1. Generates a wrapper containing **every** backend skeleton (Python ×4 +
   Java + Rust ×2 + JS), using a unique service display name per
   skeleton so the slugged directories don't collide.
2. Pre-seeds `<wrapper>/_shared/db.sqlite3` with a known `items` table
   plus a single seed row.
3. Verifies each backend can see the seed row:
   - **Python backends**: spawn the per-service `.venv` python and run
     a stdlib `sqlite3` snippet that opens the env-driven `DATABASE_URL`
     and SELECTs the row. This proves the env-loading helpers in
     `settings.py` / `core/config.py` / `app/config.py` work end-to-end.
   - **Java / Rust / Node backends**: the runner reads the wrapper
     `.env`, resolves the sqlite path the way the per-stack config
     helpers do, and confirms the seed row is visible from the same
     file the service is configured to use. Per-runtime ORM exercise is
     left to the per-skel `test_skel` runners.
4. Performs a **cross-stack round-trip**: writes a new row from one
   Python service's venv and reads it from a different Python service's
   venv, proving the data is genuinely shared rather than just the
   path being identical.
5. Skips toolchains that aren't installed (`java`, `cargo`, `node`)
   gracefully so the test runs on minimal CI hosts.

```bash
make test-shared-db          # all 8 backend skeletons (~30 s)
make test-shared-db-python   # only the 4 Python backends (~25 s)
make test-shared-db-keep     # leave _test_projects/test-shared-db on disk

# Or invoke the runner directly for finer control
_bin/test-shared-db --skel python-fastapi-skel --skel rust-actix-skel
_bin/test-shared-db --no-cross-stack  # skip the write/read round-trip
_bin/test-shared-db --no-skip          # fail (don't skip) on missing toolchains
```

Sample output:

```
Verifying every backend sees the seed row...
  ✓ python-django-skel         ( 0.03s)
  ✓ python-django-bolt-skel    ( 0.03s)
  ✓ python-fastapi-skel        ( 0.03s)
  ✓ python-flask-skel          ( 0.03s)
  ✓ java-spring-skel           ( 0.00s)
  ✓ rust-actix-skel            ( 0.00s)
  ✓ rust-axum-skel             ( 0.00s)
  ✓ js-skel                    ( 0.00s)

Cross-stack round-trip: write via python-django-skel → read via python-flask-skel
  ✓ cross-stack visibility confirmed
```

Parameters:

- `skel_type` – skeleton directory name under `_skels/` (for example `python-fastapi-skel`, `ts-react-skel`).
- `proj_name` – **leaf** wrapper directory name (no `/`), created under the current working directory.
- `service_in_proj_name` – optional **service directory base name** inside the wrapper. If omitted, a generic base is used per skeleton:
  - FastAPI/Django: `backend`
  - React: `frontend`
  - Others: `service`

Dev Skel automatically ensures that the service directory name is unique **within the project**:

- If you pass no service name, you get `backend-1`, `backend-2`, `frontend-1`, `service-1`, etc.
- If you pass an explicit name (e.g. `api`) and `api/` already exists, Dev Skel will pick `api-1/`, `api-2/`, … instead of failing.

## Makefile Commands

### Project Generation
- `make gen-<framework> NAME=myapp` - Generate a new project from a skeleton

### Testing
- `make test-generators` - Test all skeleton generators
- `make test-all` - Run tests inside each skeleton (end-to-end)
- `make test-<framework>` - Run tests for a specific skeleton

Each skeleton has a `test` script that:
- Generates a temporary project
- Runs its test suite
- Performs a non-interactive run/build check (e.g., `manage.py check`, `cargo build`, `npm run -s build`)

### Maintenance
- `make list` - List all available skeletons
- `make status` - Show status of all skeleton directories
- `make clean-all` - Clean all skeleton projects
- `make help` - Show all available commands

## Repository Layout

```
dev_skel/
├── Makefile                  # Main orchestration Makefile
├── test                      # Root test script (runs all skeleton e2e tests)
├── skel-deps                 # Main dependency installer (all skeletons)
├── _bin/                     # Helper Python CLIs and shared library
│   ├── dev_skel_lib.py       #   shared config / generation / rsync helpers
│   ├── skel_ai_lib.py        #   Ollama-backed AI generator library (stdlib only)
│   ├── skel-gen              #   canonical entrypoint — defaults to AI (new in 2026-04)
│   ├── skel-gen-ai           #   explicit Ollama-augmented generator
│   ├── skel-gen-static       #   explicit static fallback (no Ollama)
│   ├── install-dev-skel      #   install dev_skel into $DEV_DIR
│   ├── update-dev-skel       #   update $DEV_DIR from dev_skel
│   ├── sync-dev-skel         #   rsync to a remote host
│   └── skel-list             #   list available skeletons
├── .editorconfig             # Editor configuration
├── .gitignore                # Git ignore patterns
├── _skels/                   # Skeleton templates
│   ├── _common/              #   shared assets (wrapper scaffolder, manifests)
│   │   └── manifests/        #     per-skeleton AI manifests (skel-gen-ai)
│   ├── python-fastapi-skel/
│   ├── python-flask-skel/
│   ├── python-django-skel/
│   ├── python-django-bolt-skel/
│   ├── ts-react-skel/
│   ├── js-skel/
│   ├── java-spring-skel/
│   ├── rust-actix-skel/
│   └── rust-axum-skel/
└── _docs/                    # Documentation
    ├── README.md
    ├── DEPENDENCIES.md
    ├── MAKEFILE.md
    ├── SKELETONS.md
    └── LLM-MAINTENANCE.md
```

## Requirements

Each framework has specific requirements. Use `./skel-deps` to install them automatically:

- **Python**: Python 3.10+ with pip and venv
- **Node.js**: Node.js 20+ with npm
- **Java**: JDK 21+ with Maven
- **Rust**: Stable Rust with Cargo (via rustup)
- **Make**: GNU Make 4.0+

Run `./skel-deps --all` to install all dependencies, or `./skel-deps <skeleton-name>` for a specific framework. See [DEPENDENCIES.md](_docs/DEPENDENCIES.md) for details.

## Documentation

Detailed documentation is available in the `_docs/` directory:

- [Dependencies](_docs/DEPENDENCIES.md) - System dependency installation guide
- [Makefile Reference](_docs/MAKEFILE.md) - Complete documentation of all Makefile targets
- [Skeleton Templates](_docs/SKELETONS.md) - Detailed information about each skeleton
- [LLM Maintenance Guide](_docs/LLM-MAINTENANCE.md) - Guide for AI assistants maintaining this project

## Common Workflows

### Create and Test a Multi‑Service Project (Django‑Bolt + FastAPI + React)

```bash
# 1) Create wrapper + first backend (Django-Bolt) and name the service
make gen-django-bolt NAME=myproj SERVICE="Ticket Service"
cd myproj

# The wrapper now contains:
ls
#   .env  .env.example  _shared/  README.md  Makefile  services
#   run  test  build  stop  install-deps  ticket_service/

# 2) Add an Auth API as a second backend service in the same wrapper
make gen-fastapi NAME=myproj SERVICE="Auth API"          # → myproj/auth_api/

# 3) Add a React frontend as a third service
make gen-react NAME=myproj SERVICE="Web UI"              # → myproj/web_ui/

# 4) List the services the wrapper now knows about
./services
# auth_api
# ticket_service
# web_ui

# 5) Every service in the wrapper shares the same database, JWT secret,
#    and BACKEND_URL via .env
cat .env | grep -E 'DATABASE_URL|JWT_SECRET|BACKEND_URL'
# DATABASE_URL=sqlite:///_shared/db.sqlite3
# JWT_SECRET=change-me-32-bytes-of-random-data
# BACKEND_URL=http://localhost:8000   # the React frontend talks to this
#
# The React skeleton's `src/api/items.ts` calls
# `${BACKEND_URL}/api/items` and `src/state/state-api.ts` calls
# `${BACKEND_URL}/api/state` — both endpoints are served by the
# django-bolt backend out of the box. Point BACKEND_URL at any other
# backend (e.g. SERVICE_URL_AUTH_API from _shared/service-urls.env)
# to swap the data source without touching React code.

# 6) Run tests for one service or all services
./test ticket_service          # only this service's tests
./test                          # fan out to every service that has ./test

# 7) Run the dev server for one specific service
./run ticket_service dev        # python manage.py runbolt --dev
./run auth_api dev              # uvicorn ...
./run web_ui dev                # vite dev

# 8) Install deps across every service in one go
./install-deps                  # fans out to every service
```

Generating two services with the same name auto‑suffixes the slug
(`ticket_service-1`, `ticket_service-2`, ...). Re‑running the generator
into an existing wrapper preserves the wrapper `.env`, the
`_shared/db.sqlite3` database, and any service directories that already
exist.

Each inner service directory (`backend-1/`, `frontend-1/`, `service-1/`, etc.) contains its own framework‑specific `README.md`, configuration, and scripts. The wrapper just provides a unified entrypoint so you can work with the project as a whole.

### Wrapper‑Level Scripts

Every generated project wrapper includes these scripts:

| Script | Description |
|--------|-------------|
| `./test` | Run project tests for the active service |
| `./build` | Build Docker image (or local build with `--local`/`--jar`/`--release`) for the active service |
| `./run` | Run server for the active service (modes: `dev`, `prod`, `docker`) |
| `./stop` | Stop running Docker containers for the active service |

These scripts live in the top‑level wrapper directory you passed as `NAME` and **forward all arguments** to matching scripts in a chosen inner service directory (for example `backend-1/`, `frontend-1/`, `service-1/`).

Run any script with `-h` or `--help` to see available options provided by the underlying skeleton.

### Test All Generators

```bash
make test-generators
```

This creates test projects for all frameworks and verifies they build correctly.

## Implementation Details (for Contributors)

- Each skeleton defines a `merge` script used during generation. Skeleton Makefiles reference it as:
  - `MERGE := $(SKEL_DIR)/merge`
  - `bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"`
- Each skeleton includes:
  - `gen` script: contains **all** generation logic; skeleton Makefiles delegate to it via `bash $(SKEL_DIR)/gen "$(NAME)"`.
  - `test` script: end‑to‑end test that generates into a temp dir and validates the project.
- The `_bin/skel-gen` tool prefers a skeleton's `gen` script when present and falls back to `make -C <skel> gen NAME=<target> SERVICE=<service_subdir>`.

The `_skels/_common/common-wrapper.sh` script is used by multiple skeletons to set up the wrapper directory. It:

- Writes a generic wrapper `README.md` and `Makefile`.
- Scans a chosen service directory and generates thin wrapper scripts in the wrapper that forward into that service.

When you add additional services to the same wrapper later (for example a React frontend to a FastAPI backend project), the wrapper README/Makefile and scripts are simply refreshed.

## Roadmap – Towards Fully Integrated Multi‑Service Projects

The current implementation is intentionally simple: you can create multiple services under one wrapper and manage each service with its own scripts and tooling. The long‑term vision is to make Dev Skel a **full multi‑service orchestration toolkit**.

Planned directions (high‑level roadmap):

1. **Richer multi‑service project model**
   - First‑class support for describing all services in a project (backends, frontends, workers, gateways) in a single project configuration file.
   - Helpers to list and inspect services (`make services`, `./services list`).

2. **Shared contracts and types between services**
   - Central definitions for API contracts, DTOs, and domain types (for example via OpenAPI, protobuf, JSON Schema, or a dedicated schema DSL).
   - Code generation to emit type‑safe models for multiple runtimes (Python, TypeScript, Rust) from a single source of truth.
   - Consistent validation and serialization across services.

3. **Integrated API protocols and routing**
   - Conventions for HTTP/REST, gRPC, and messaging endpoints so services expose predictable interfaces.
   - Automatic wiring of service URLs and ports in local dev and test environments.
   - Optional API gateway / reverse proxy service pre‑configured for common patterns.

4. **Automatic local deployment stacks**
   - Generate Dockerfiles and Docker Compose files that spin up all services in a project together, plus supporting infrastructure like:
     - Database server(s) (PostgreSQL, etc.).
     - HTTP reverse proxy.
     - Message broker / streaming (Kafka, etc.).
     - Monitoring stack (Prometheus / Grafana or similar).
   - Helper scripts in the wrapper to bring the whole stack up/down in one command.

5. **Kubernetes and Helm integration**
   - Optional generators that produce Kubernetes manifests and Helm charts for all services in a project.
   - Opinionated defaults for namespaces, ingress, secrets, config maps, and per‑service autoscaling.
   - CI‑friendly hooks to build and deploy to test clusters.

6. **Built‑in observability and diagnostics**
   - Each skeleton upgraded to emit structured logs, metrics, and traces by default.
   - Common dashboards and alerts bundled for frequently used stacks (FastAPI + React, Django + React, Actix APIs, etc.).
   - Helpers to correlate requests across services using trace IDs.

7. **Project‑level orchestration and aggregation**
   - Project‑level commands that operate across all services (test, lint, format, build) with clear summaries.
   - Tools to visualize the service graph (which services talk to which, shared contracts, data flows).
   - Improved UX for managing multiple environments (dev, staging, prod) from the same project.

As these roadmap items are implemented, the documentation and individual skeleton guides will be updated to describe the new capabilities and how to opt in.

## License

This project provides skeleton templates for various frameworks. Each generated project may be subject to the license terms of its respective framework and dependencies.
