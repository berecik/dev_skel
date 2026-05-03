# Agents Rules for `wrapper-skel`

The wrapper-skel template generates the **project basement** — the
shared layer that every service in a multi-service `dev_skel` project
sits inside. It owns the wrapper directory, not any specific service.

## What this skel produces

Running `make -C _skels/wrapper-skel gen NAME=/abs/path/to/wrapper`
lays down:

- `.env` / `.env.example` — single source of truth for `DATABASE_URL`,
  `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_ACCESS_TTL`,
  `JWT_REFRESH_TTL`, default seed accounts, OLLAMA_HOST.
- `_shared/db.sqlite3` — touched empty SQLite file; the default shared
  database every backend reads when `DATABASE_URL` is the default
  `sqlite:///_shared/db.sqlite3` value.
- `_shared/service-urls.env` — generated map of `SERVICE_PORT_*` /
  `SERVICE_URL_*` entries, kept current on every service add.
- `contracts/openapi/wrapper-api.yaml` — canonical wrapper API spec.
- `docker-compose.yml` — Postgres backing service + (later, when the
  user adds backends with Dockerfiles) per-service container entries.
- `README.md`, `Makefile` — wrapper-level docs and convenience
  targets.
- `./services` — service discovery script (lists every directory
  with a `.skel_context.json` sidecar).
- `./project` / `./env` / `./kube` — project metadata, env helper,
  k8s/Helm lifecycle entry point.
- `./run-dev-all` / `./stop-dev-all` — multi-service dev launcher.
- `dev_skel.project.yml` — project metadata for AI agents to discover
  which services exist and which skel produced each one.

The per-service dispatch wrappers (`./run`, `./test`, `./build`,
`./stop`, `./install-deps`, `./ai`, `./backport`) are NOT created
in wrapper-only mode — they are emitted on the first
`make gen-<service-skel>` because their content is derived from the
service scripts that exist.

## Composition with service skels

Two flows are supported:

**1. Wrapper first, services later.**

```bash
make gen-wrapper NAME=myproj                 # basement only
make gen-fastapi NAME=myproj SERVICE="API"   # add a backend
make gen-react   NAME=myproj SERVICE="UI"    # add a frontend
```

**2. Service-driven (existing flow, unchanged).**

```bash
make gen-fastapi NAME=myproj SERVICE="API"   # creates myproj/ + basement + service in one shot
```

Both flows share the same `_skels/_common/common-wrapper.sh`
implementation; flow 1 calls it with empty `PROJECT_SUBDIR`, flow 2
calls it with the just-generated service slug. Calling
`common-wrapper.sh` twice on the same wrapper is idempotent.

## Skeleton rules for AI agents

1. **Never hardcode wrapper-level files in a service skel.** Anything
   shared (env, README, dispatch scripts, k8s manifests) belongs in
   `wrapper-skel` (and its delegate `_skels/_common/common-wrapper.sh`).
2. **Service skels do not own the basement.** A service skel's `gen`
   script:
   - Creates its service directory.
   - Calls `common-wrapper.sh "$MAIN_DIR" "$PROJECT_SUBDIR" "$TITLE"`.
   The `common-wrapper.sh` invocation handles wrapper bootstrap on
   first call and updates the wrapper on subsequent calls.
3. **Edits to the wrapper layout go in one place.** Both
   `wrapper-skel/gen` and per-service `gen` scripts route through
   `_skels/_common/common-wrapper.sh`, so changing wrapper output is a
   single-file edit. Don't duplicate wrapper code into service skels.

## Tests

```bash
bash _skels/wrapper-skel/test_skel        # skeleton-level smoke
make test-gen-wrapper                     # top-level gen test
make test-generators                      # full generator test suite
```

`test_skel` generates into a temp dir, asserts the canonical wrapper
files exist, asserts the README rendered the `<service>` placeholder,
and cleans up.
