# Skeleton Design Guide

This document is the authoritative reference for designing, creating,
and updating dev_skel skeletons. Every skeleton in the catalogue must
follow the conventions described here to interoperate with the
generator (`skel-gen-ai`), the in-service code agent (`./ai`), the
template ↔ service sync (`./backport` + `./ai upgrade`), the wrapper
dispatcher, and the cross-stack integration tests.

---

## 1. What a skeleton is

A **skeleton** is a working project template that lives at
`_skels/<language>-<framework>-skel/`. When a user runs `skel-gen`
(or `skel-gen-ai`), the skeleton's `gen` script copies itself into a
**service subdirectory** inside a **wrapper project**:

```
_skels/python-fastapi-skel/     ← the skeleton (template)
           ↓  gen
myproj/                         ← the wrapper
├── .env                        ← shared environment
├── _shared/db.sqlite3          ← shared database
├── items_api/                  ← generated service (from the skel)
│   ├── (source tree)
│   ├── ./ai                    ← in-service code agent
│   ├── ./backport              ← service → template sync
│   └── .skel_context.json      ← sidecar (skeleton_name, skeleton_version)
└── web_ui/                     ← another service (from ts-react-skel)
```

The skeleton is the blueprint; the generated service is the instance.
Multiple services from different skeletons can coexist in one wrapper.
They share the wrapper's `.env`, database, JWT secret, and dispatch
scripts.

---

## 2. Required files

Every skeleton **must** ship:

| File | Purpose |
| ---- | ------- |
| `gen` | Bash script. Entry point for generation. Creates the service subdir, calls `merge`, does stack-specific setup, calls `common-wrapper.sh`. |
| `merge` | Bash script. Copies skeleton files into the target without overwriting user edits. Idempotent. |
| `test` or `test_skel` | Bash script. Generates a throwaway project and runs its test suite. Used by `make test-generators` in CI. |
| `VERSION` | Plain text semver (e.g. `0.1.0`). Read by `install-ai-script` to populate the sidecar. Bumped by `./backport apply`. |
| `CHANGELOG.md` | Keep-a-Changelog format. Appended by `./backport apply` on every accepted service-to-template change. |
| `Makefile` | Skeleton-level Make targets (`gen`, `test`). |
| `AGENTS.md` | Cross-agent rules rendered into generated projects. |
| `CLAUDE.md` | Claude Code-specific rules rendered into generated projects. |
| `JUNIE-RULES.md` | Junie-specific rules rendered into generated projects. |

**Strongly recommended:**

| File | Purpose |
| ---- | ------- |
| `deps` | Bash script. Installs system-level toolchain dependencies (called by `./skel-deps`). |
| `install-deps` | Bash script. Installs per-project dependencies (npm install, pip install, etc.). **This file is the service marker** — `common-wrapper.sh` discovers services by looking for an executable `install-deps`. |
| `Dockerfile` | Multi-stage build: builder → production → development. |
| `.devcontainer/` | VS Code Dev Containers: `devcontainer.json` + `Dockerfile` + `docker-compose.devcontainer.yml`. |
| `.dockerignore` | Per-stack Docker build exclusions. |
| `.env.example` | Template for the service-local `.env` (seeded on first gen). |

---

## 3. The gen / merge / test contract

### `gen <main-dir> [service-name]`

1. Accept `<main-dir>` (absolute path to the wrapper directory) and
   optional `<service-name>` (display name like `"Ticket Service"`).
2. Slugify the service name (`slugify_service_name` from
   `_common/slug.sh`) → e.g. `ticket_service`. Default to a
   stack-specific slug (`backend`, `frontend`, `service`, `app`).
3. Create `$MAIN_DIR/$PROJECT_SUBDIR/`.
4. Call `bash "$SKEL_DIR/merge" "$SKEL_DIR" "$PROJECT_DIR"`.
5. Stack-specific setup: create venv, `npm install`, `cargo fetch`, etc.
6. **Export `SKEL_NAME`** before calling common-wrapper:
   ```bash
   export SKEL_NAME="$(basename "$SKEL_DIR")"
   bash "$COMMON_DIR/common-wrapper.sh" "$MAIN_DIR" "$PROJECT_SUBDIR"
   ```

### `merge <skel-dir> <target-dir>`

1. Walk every file in `<skel-dir>` via `find -type f -print0`.
2. Skip generator-owned files (`Makefile`, `merge`, `gen`, `test_skel`,
   `deps`, `package-lock.json`). Also skip build artefacts
   (`.venv/`, `node_modules/`, `target/`, `__pycache__/`, etc.).
3. For each surviving file:
   - If it matches `OVERWRITE_PATTERN` → always overwrite.
   - Otherwise → copy only if the destination doesn't exist.
4. The **OVERWRITE_PATTERN** is how a skeleton forces specific files
   to stay in sync with the template even on re-runs. Example from
   `ts-react-skel/merge`:
   ```bash
   OVERWRITE_PATTERN="package\.json|tsconfig\.json|vite\.config\.ts|src/api/.*|src/auth/.*"
   ```
   Every new file you add to the skeleton that must survive re-runs
   needs to be listed here.

**Invariant:** `merge` is idempotent. Running it twice produces the
same result.

### `test` or `test_skel`

1. Generate a project into a temp directory.
2. Run the generated service's own `./test` script.
3. Optionally build a Docker image (`./build --tag=...`).
4. Clean up the temp directory.

Use `test_skel` when the top-level `test` name would collide with a
framework convention (e.g. Django's `test` directory).

---

## 4. Wrapper integration (`common-wrapper.sh`)

After every per-skel `gen` call, the skeleton calls:

```bash
export SKEL_NAME="$(basename "$SKEL_DIR")"
bash "$COMMON_DIR/common-wrapper.sh" "$MAIN_DIR" "$PROJECT_SUBDIR"
```

This script is **idempotent** (safe to re-run) and:

1. **Seeds `<wrapper>/.env`** from `.env.example` on first run.
   Subsequent runs preserve the existing `.env`.
2. **Generates `_shared/service-urls.env`** with one
   `SERVICE_URL_<UPPER_SLUG>=http://...` per discovered service.
   Ports are allocated sequentially from `SERVICE_PORT_BASE` (default
   8000), preserving previously-assigned ports.
3. **Seeds `<wrapper>/docker-compose.yml`** with a Postgres backing
   service on first run.
4. **Installs the AI machinery** into every service via
   `_skels/_common/refactor_runtime/install-ai-script`:
   - `./ai` — the in-service code agent.
   - `.ai_runtime.py` — vendored runtime.
   - `./backport` — service → template sync.
   - `.skel_context.json` — sidecar with `skeleton_name`,
     `skeleton_version` (from `$SKEL_DIR/VERSION`), `generated_at`.
   - Appends `.ai/` to `.gitignore`.
5. **Generates dispatch scripts** — `run`, `test`, `build`, `stop`,
   `install-deps`, `ai`, `backport`, etc. Each sources
   `<wrapper>/.env` before dispatching.

### Dispatch modes

| Mode | Scripts | Default behavior |
| ---- | ------- | ---------------- |
| **Single-shot** | `run`, `run-dev`, `lint`, `format`, `deps` | Run on the first service that has the script |
| **Fan-out** | `test`, `build`, `stop`, `install-deps`, `ai`, `backport` | Run on every service that has the script |

All dispatch scripts accept an optional first arg matching a service
slug to scope to one service: `./ai items_api "add pagination"`.

---

## 5. Backend environment contract

Every backend **must** read its configuration from environment
variables loaded from `<wrapper>/.env`. The shared keys are:

```ini
# Database — same store for every service
DATABASE_URL=sqlite:///_shared/db.sqlite3
DATABASE_JDBC_URL=jdbc:sqlite:_shared/db.sqlite3
SPRING_DATASOURCE_URL=jdbc:sqlite:_shared/db.sqlite3

# JWT — same secret so a token from one service is accepted by all
JWT_SECRET=change-me-32-bytes-of-random-data
JWT_ALGORITHM=HS256
JWT_ISSUER=devskel
JWT_ACCESS_TTL=3600
JWT_REFRESH_TTL=604800

# Default backend URL for frontends
BACKEND_URL=http://localhost:8000
```

**Rules:**
- **Never hardcode** a database URL, JWT secret, or sqlite path.
- Each stack ships a config helper that loads `<service>/.env` first,
  then `<wrapper>/.env` (dotenv's "first wins" semantics mean local
  overrides survive).
- Per-stack helpers:

| Stack | Config module | JWT exposure |
| ----- | ------------- | ------------ |
| Django / Django-Bolt | `settings.py` / `_build_databases()` | `settings.JWT_*` |
| FastAPI | `core/config.py` / `_resolve_database_url()` | `config.JWT_*` |
| Flask | `app/config.py` | `config.JWT_*` |
| Spring Boot | `application.properties` + `JwtProperties` bean | `@ConfigurationProperties` |
| Rust (Actix / Axum) | `src/config.rs::Config::from_env()` | `Config.jwt_*` in `AppState` |
| Next.js | `src/config.js` (dotenv) | `config.jwt.*` |
| React (Vite) | `vite.config.ts` env plugin (build-time) | `config.backendUrl` (never `JWT_SECRET`) |
| Flutter | `flutter_dotenv` (runtime bundled asset) | `flutter_secure_storage` for bearer token |

---

## 6. Wrapper-shared API contract

Every backend skeleton that ships the wrapper-shared API must
implement these endpoints. Both frontends (React, Flutter) call them
against `BACKEND_URL`. The cross-stack integration test
(`_bin/_frontend_backend_lib.py`) is the source of truth.

### Authentication

```
POST /api/auth/register
  Body:     {username, email, password, password_confirm}
  Response: 201 {user: {id, username, email}}

POST /api/auth/login
  Body:     {username, password}
  Response: 200 {access: "<jwt>"}
```

All subsequent endpoints require `Authorization: Bearer <jwt>`.
Anonymous or invalid-token requests must return 401 or 403.

### Items (CRUD + complete action)

```
GET    /api/items           → 200 [{id, name, description, is_completed, category_id, created_at, updated_at}]
POST   /api/items           → 201 {id, name, description, is_completed, category_id, ...}
  Body: {name, description?, is_completed?, category_id?}
GET    /api/items/{id}      → 200 {id, name, description, is_completed, category_id, ...}
POST   /api/items/{id}/complete → 200 {id, ..., is_completed: true}
```

**Field types:**
- `id`: integer
- `name`: string (required, max 255)
- `description`: string or null (optional, defaults to null/"")
- `is_completed`: boolean (defaults to false) — stored as INTEGER 0/1
  in SQLite, must be returned as JSON `true`/`false`
- `category_id`: integer or null (optional FK to `categories.id`)
- `created_at`, `updated_at`: ISO 8601 datetime strings

### Categories (CRUD)

```
GET    /api/categories           → 200 [{id, name, description, created_at, updated_at}]
POST   /api/categories           → 201 {id, name, description, ...}
  Body: {name, description?}
GET    /api/categories/{id}      → 200 {id, name, description, ...}
PUT    /api/categories/{id}      → 200 {id, name, description, ...}
  Body: {name?, description?}
DELETE /api/categories/{id}      → 204 (empty body)
```

Categories are **shared** (not per-user) but **auth-protected** — any
authenticated user can CRUD them. The `name` field is unique.
Deleting a category sets `items.category_id = NULL` for referencing
items (SET_NULL, no cascade).

**Field types:**
- `id`: integer
- `name`: string (required, unique, max 255)
- `description`: string or null
- `created_at`, `updated_at`: ISO 8601 datetime strings

### State (per-user key/value store)

```
GET    /api/state           → 200 {key: jsonString, ...}
PUT    /api/state/{key}     → 200 {key, value, updated_at}
  Body: {value: "<json string>"}
DELETE /api/state/{key}     → 200 {deleted: key}
```

Per-user, keyed by `(user_id, key)` unique constraint. The `value`
field is a JSON string — the backend stores it opaquely and the
frontend handles encode/decode.

### Database schema (SQLite reference)

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  email TEXT,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  is_completed INTEGER NOT NULL DEFAULT 0,
  category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  owner_id INTEGER REFERENCES users(id),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE react_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  key TEXT NOT NULL,
  value TEXT NOT NULL DEFAULT '""',
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, key)
);
```

---

## 7. AI manifests

Each AI-aware skeleton ships a manifest at
`_skels/_common/manifests/<skeleton-name>.py`. The manifest tells
`skel-gen-ai` which files Ollama should rewrite for the user's
`{item_class}` entity.

### Structure

```python
SYSTEM_PROMPT = """..."""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": "post-generation hint",
    "targets": [
        {
            "path": "{service_slug}/models.py",
            "template": "app/example_items/models.py",
            "language": "python",
            "description": "Entity model",
            "prompt": "Rewrite this module for {item_class}..."
        },
    ]
}

# Optional: cross-service integration phase
INTEGRATION_MANIFEST = {
    "system_prompt": "...",
    "targets": [...],
    "test_command": "./test",
    "fix_timeout_m": 120,
}
```

### Available placeholders

| Placeholder | Value |
| ----------- | ----- |
| `{skeleton_name}` | e.g. `python-fastapi-skel` |
| `{project_name}` | e.g. `myproj` |
| `{service_subdir}` | e.g. `items_api` |
| `{service_slug}` | same as subdir |
| `{item_name}` | e.g. `ticket` (lowercase) |
| `{item_class}` | e.g. `Ticket` (PascalCase) |
| `{items_plural}` | e.g. `tickets` (snake_case plural) |
| `{auth_type}` | e.g. `jwt` |
| `{template}` | contents of the referenced template file |
| `{retrieved_context}` | RAG-retrieved skeleton chunks (opt-in) |
| `{wrapper_snapshot}` / `{retrieved_siblings}` | sibling service metadata (integration phase) |
| `{backend_extra}` / `{frontend_extra}` / `{integration_extra}` | user-supplied custom prompts |

### Quality features (automatic)

The AI pipeline includes three quality mechanisms that run
automatically during generation:

* **Multi-phase context** — each target sees the outputs of all
  earlier targets via the `{prior_outputs}` placeholder. Later
  targets (tests, routes) see the exact code earlier targets (models,
  schemas) produced, keeping field names and imports consistent.
* **Auto-retry** (`--max-retries N`, default 1) — if the generated
  code fails the per-skel validator (`cargo check`, `mvn package`,
  `tsc --noEmit`, `flutter analyze`, `py_compile`), the runner cleans
  up and re-runs the full generation.
* **Structured critique loop** (`--critique`, default on) — after
  generating each file, the model reviews it against the system
  prompt's CRITICAL/Coding rules sections. On FAIL, the file is
  re-generated with the critique reason appended as extra context.

### Rules for manifest authors

1. **Never tell the LLM to hardcode** a database URL, JWT secret, or
   sqlite path. Always reference the config module.
2. When `{auth_type} == 'none'`, drop owner-isolation checks.
3. Mark wrapper-shared models (Item, Category, ReactState) as
   **"MUST be preserved verbatim"** so the AI doesn't rename or
   restructure them.
4. Targets are **additive** — Phase 1 files are never overwritten in
   Phase 3 (integration).
5. **Include literal compilable code blocks** in prompts for
   typed-language skeletons (Rust, Java, TypeScript, Dart). The model
   follows concrete code examples much more reliably than abstract
   descriptions. Show the exact struct/record/interface shape, the
   exact import paths, and the exact function signatures.
6. **Don't regenerate entry-point files** (`main.rs`, `main.dart`,
   `App.tsx`) when the new entity would cause type mismatches with
   parameters the entry point already declares. Instead, generate
   the new module as a standalone file and let the user or the
   INTEGRATION_MANIFEST wire it in.

---

## 8. Versioning + service ↔ template sync

### VERSION + CHANGELOG

Each skeleton ships `VERSION` (semver) and `CHANGELOG.md`:

- **`./backport apply`** (service → template): writes changed files
  back to `_skels/<skel>/`, bumps `VERSION` by a patch, and prepends
  a Keep-a-Changelog entry listing every backported file.
- **`./ai upgrade`** (template → service): reads
  `.skel_context.json::skeleton_version`, compares to `<skel>/VERSION`,
  extracts the matching CHANGELOG entries, synthesises an AI request
  to apply those changes. On success, rewrites the sidecar.

### Sidecar: `.skel_context.json`

Written by `install-ai-script` on every gen:
```json
{
  "skeleton_name": "python-fastapi-skel",
  "skeleton_path_rel": "_skels/python-fastapi-skel",
  "skeleton_version": "0.1.0",
  "generated_at": "2026-04-17T..."
}
```

---

## 9. Docker + devcontainer conventions

### Dockerfile (multi-stage)

Every skeleton should ship a Dockerfile with at least two stages:

```dockerfile
# Builder stage — install deps, compile
FROM <base>:version AS builder
...

# Production stage — minimal image, non-root user, healthcheck
FROM <base>:version AS production
...
HEALTHCHECK --interval=30s ...
CMD [...]

# Development stage — full dev tools, hot reload
FROM <base>:version AS development
...
CMD [..., "--reload"]
```

### .devcontainer/

Three files:
- `devcontainer.json` — compose reference, per-stack VS Code
  extensions, port forwarding, `postCreateCommand`.
- `Dockerfile` — based on `mcr.microsoft.com/devcontainers/<lang>`.
- `docker-compose.devcontainer.yml` — devcontainer service + Postgres
  backing service (for backends).

### .dockerignore

Concise per-stack exclusions. Common entries:
```
.git
.devcontainer
.ai
.ai_runtime.py
.skel_context.json
*.md
VERSION
CHANGELOG.md
Makefile
merge
gen
test_skel
deps
```

Plus stack-specific: `.venv/`, `node_modules/`, `target/`, etc.

---

## 10. Per-skeleton rules documents

Each skeleton ships `AGENTS.md`, `CLAUDE.md`, and `JUNIE-RULES.md`.
These are **rendered into generated projects** with placeholders:

| Placeholder | Value |
| ----------- | ----- |
| `${project_name}` | e.g. `myproj` |
| `${service_dir}` | e.g. `items_api/` |
| `${skeleton_name}` | e.g. `python-fastapi-skel` |
| `${skeleton_doc}` | e.g. `_docs/python-fastapi-skel.md` |

The templates live at `_skels/_common/AGENTS.md`,
`_skels/_common/CLAUDE.md`, `_skels/_common/JUNIE-RULES.md`. The
rendering happens via `dev_skel_lib.render_agents_template`.

Per-skeleton overrides live at `_skels/<name>/AGENTS.md` etc. and
take precedence over the common templates.

---

## 11. How to create a NEW skeleton

Step-by-step:

### A. Create the directory

```bash
mkdir -p _skels/<lang>-<framework>-skel
cd _skels/<lang>-<framework>-skel
```

### B. Write the source tree

Build a working application with your chosen framework. It should:
- Read DATABASE_URL and JWT_* from the environment (see § 5).
- Ship an example CRUD entity (conventionally called `Item` or
  `example_items`).
- Implement the wrapper-shared API contract (see § 6) if it's a
  backend.
- Include a test suite that runs via `./test`.

### C. Write the generator scripts

**`gen`:**
```bash
#!/usr/bin/env bash
set -euo pipefail
SKEL_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMON_DIR="$SKEL_DIR/../_common"
. "$COMMON_DIR/slug.sh"

MAIN_DIR="${1:-}"
SERVICE_NAME_RAW="${2:-}"
# ... slugify, create subdir, call merge, stack setup ...
export SKEL_NAME="$(basename "$SKEL_DIR")"
bash "$COMMON_DIR/common-wrapper.sh" "$MAIN_DIR" "$PROJECT_SUBDIR"
```

**`merge`:** Copy every file except generator-owned ones. See § 3.

**`test` or `test_skel`:** Generate into a temp dir, run tests, clean up.

### D. Add metadata

```bash
echo "0.1.0" > VERSION
cat > CHANGELOG.md << 'EOF'
# Changelog

## [0.1.0] - $(date +%Y-%m-%d)
- Initial version.
EOF
```

### E. Add Docker support

Write `Dockerfile` (multi-stage), `.devcontainer/` (3 files),
`.dockerignore`.

### F. Add rules documents

Copy `AGENTS.md`, `CLAUDE.md`, `JUNIE-RULES.md` from a similar
skeleton and adapt.

### G. Add an AI manifest (optional but recommended)

Create `_skels/_common/manifests/<name>-skel.py` with a `MANIFEST`
dict listing the files Ollama should rewrite.

### H. Wire into the top-level Makefile

```makefile
NEW_SKEL := $(SKEL_DIR)/<name>-skel
SKELETONS := ... $(NEW_SKEL)

gen-<short>: ## Generate <Name> project (NAME=myapp)
    @bash $(NEW_SKEL)/gen "$(NAME)"

test-gen-<short>: ## Test <Name> generator
    @$(MAKE) gen-<short> NAME=$(TEST_OUTPUT)/test-<short>-app
    @echo "$(GREEN)<Name> generator test passed$(NC)"
```

Add the new target to `test-generators:` and `.PHONY:`.

### I. Add documentation

- Create `_docs/<name>-skel.md` with endpoint reference, stack
  details, quick start, Docker usage.
- Add a row to the catalogue table in `_docs/SKELETONS.md`.
- Add cross-stack test runner at `_bin/skel-test-react-<short>` if
  the skeleton is a backend that ships the items API.

### J. Verify

```bash
make test-generators          # all gen scripts work
make test-<short>             # skeleton self-test
make test-react-<short>       # cross-stack (if applicable)
```

---

## 12. How to update an EXISTING skeleton

### A. Edit the skeleton source

Make your changes directly in `_skels/<name>-skel/`. The skeleton's
source tree is the template — changes here affect all future
generations.

### B. Bump VERSION + CHANGELOG

```bash
# Bump patch: 0.1.0 → 0.1.1
echo "0.1.1" > VERSION

# Prepend a changelog entry
cat > /tmp/entry << 'EOF'
## [0.1.1] - 2026-04-17
- Added /api/categories CRUD endpoints.
- Added category_id FK to items table.
EOF
# Insert after the "# Changelog" header
```

Or let `./backport apply` do this automatically (if the change
originates in a generated service).

### C. Update the AI manifest (if applicable)

If the change affects files listed in the manifest's `targets`, update
the prompts to reflect the new structure. If the change adds a new
wrapper-shared model (like Category), add it to the "MUST be
preserved verbatim" list.

### D. Update rules documents

If the change affects behavior described in `AGENTS.md`, `CLAUDE.md`,
or `JUNIE-RULES.md`, update them.

### E. Update merge OVERWRITE_PATTERN (if applicable)

If you added a new file that must survive re-runs against existing
wrappers, add it to the merge script's `OVERWRITE_PATTERN`.

### F. Run tests

```bash
make test-generators          # all gen scripts still work
make test-<framework>         # skel self-test
make test-react-<framework>   # cross-stack (if applicable)
```

### G. Propagate to existing services

Users with already-generated services can pull the change via:

```bash
cd myproj/items_api
./ai upgrade                  # dry-run: shows the changelog excerpt
./ai upgrade --apply          # apply via the AI propose/apply flow
```

Or manually:
```bash
./backport propose            # see what differs
# (user applies changes by hand)
```

---

## Appendix: skeleton catalogue

| Skeleton | Kind | AI manifest | Items API | Default slug |
| -------- | ---- | ----------- | --------- | ------------ |
| `python-fastapi-skel` | backend | ✓ | server | `backend/` |
| `python-fastapi-rag-skel` | backend | — | server | `backend/` |
| `python-django-skel` | backend | ✓ | — | `backend/` |
| `python-django-bolt-skel` | backend | ✓ | server | `backend/` |
| `python-flask-skel` | backend | ✓ | — | `backend/` |
| `java-spring-skel` | backend | ✓ | — | `service/` |
| `rust-actix-skel` | backend | ✓ | — | `service/` |
| `rust-axum-skel` | backend | ✓ | — | `service/` |
| `go-skel` | backend | — | — | `service/` |
| `next-js-skel` | backend | ✓ | server | `app/` |
| `ts-react-skel` | frontend | ✓ | client | `frontend/` |
| `flutter-skel` | frontend | ✓ | client | `frontend/` |

**server** = ships `/api/items` + `/api/categories` + `/api/auth` +
`/api/state`. **client** = ships typed fetch/HTTP clients that call
those endpoints via `BACKEND_URL`.
