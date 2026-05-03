#!/usr/bin/env bash
set -euo pipefail

# Common wrapper scaffolder for generated multi-service projects.
#
# Usage:
#   common-wrapper.sh MAIN_DIR PROJECT_SUBDIR [PROJECT_TITLE]
#
# Where MAIN_DIR is the wrapper directory (e.g. ./myproj) and PROJECT_SUBDIR
# is the slug of the service that was just generated inside it (e.g.
# `ticket_service`).
#
# What this script produces in MAIN_DIR (idempotent — safe to re-run as more
# services are added to the same wrapper):
#
#   .env / .env.example      Shared environment for every service in the
#                            wrapper. Holds the common DATABASE_URL, JWT
#                            secret, and per-component DATABASE_* / JWT_*
#                            fallback variables. `.env` is created on the
#                            first run only; `.env.example` is always
#                            refreshed so the documented baseline stays in
#                            sync with the scaffolder.
#
#   _shared/README.md        Explains the shared layer, points at the
#                            authoritative env file, and tells the user how
#                            to swap sqlite for postgres.
#
#   _shared/db.sqlite3       (touched only — empty DB file used as the
#                            default shared SQLite database.)
#
#   README.md / Makefile     Wrapper-level docs and convenience targets.
#
#   ./services               Discovery script that lists every service
#                            currently in the wrapper.
#
#   ./run /test /build /stop /install-deps / lint / format /deps
#       Multi-service dispatch wrappers. Each:
#         - Sources <main_dir>/.env so child processes inherit shared vars.
#         - Accepts an optional first arg matching a service slug, in which
#           case it forwards to <slug>/<script>.
#         - Otherwise picks a sensible default per script:
#             run     → first service that has the script
#             test    → run on every service that has the script
#             stop    → run on every service that has the script
#             build   → run on every service that has the script
#             install-deps → run on every service that has the script
#             others  → first service that has the script

MAIN_DIR="${1:?main_dir missing}"
PROJECT_SUBDIR="${2-}"
PROJECT_TITLE="${3:-Generated Project}"

# Wrapper-only mode (no service yet): pass an empty PROJECT_SUBDIR. The
# scaffolder still lays down .env, _shared/, README, Makefile, dispatch
# scripts, project/env/kube helpers, etc. — every service-specific
# block (existence check, docker-compose entry, AI sidecar force-overwrite,
# service-name references in README) is gated on PROJECT_SUBDIR being
# non-empty so calling this twice (once wrapper-only, once per added
# service) is safe.

MAIN_DIR="$(cd "$MAIN_DIR" && pwd)"
PROJECT_DIR=""
if [[ -n "$PROJECT_SUBDIR" ]]; then
  PROJECT_DIR="$MAIN_DIR/$PROJECT_SUBDIR"
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "[common-wrapper] ERROR: project dir '$PROJECT_DIR' does not exist" >&2
    exit 1
  fi
  echo "[common-wrapper] Preparing wrapper in: $MAIN_DIR (project: $PROJECT_SUBDIR)"
else
  echo "[common-wrapper] Preparing wrapper in: $MAIN_DIR (no service yet)"
fi
mkdir -p "$MAIN_DIR" "$MAIN_DIR/_shared"

# --------------------------------------------------------------------------- #
#  1) Shared environment
# --------------------------------------------------------------------------- #

# Always (re)write the example so the documented baseline stays current.
cat >"$MAIN_DIR/.env.example" <<'EOF'
# ----- Shared environment for every service in this wrapper ---------------- #
#
# Loaded by every backend service before its own local .env. Edit `.env`
# (a copy of this file) to change values for the whole project at once;
# per-service `.env` files inside <service>/ override what is set here.
#
# A live `.env` was created on first generation if it did not already exist.
# Commit `.env.example` but NOT `.env` (the latter usually holds secrets).

# ----- Database ------------------------------------------------------------ #
# Default: a single shared SQLite file at _shared/db.sqlite3.
# To switch to Postgres, set DATABASE_URL (and DATABASE_JDBC_URL for the JVM
# stack) to a postgresql://... URL and the per-component DATABASE_* fallback
# values become unused.
#
# DATABASE_URL is the abstract / Python form (sqlx, sqlalchemy, django,
# flask all understand it). DATABASE_JDBC_URL is the JVM-friendly variant
# used by Spring Boot's spring.datasource.url property — both should point
# at the same store. Keep them in sync.
DATABASE_URL=sqlite:///_shared/db.sqlite3
DATABASE_JDBC_URL=jdbc:sqlite:_shared/db.sqlite3
DATABASE_ENGINE=sqlite
DATABASE_NAME=_shared/db.sqlite3
DATABASE_HOST=
DATABASE_PORT=
DATABASE_USER=
DATABASE_PASSWORD=

# Spring Boot picks these up natively (relaxed binding). They mirror
# DATABASE_JDBC_URL / DATABASE_USER / DATABASE_PASSWORD so any JVM service
# in the wrapper just works without extra wiring.
SPRING_DATASOURCE_URL=jdbc:sqlite:_shared/db.sqlite3
SPRING_DATASOURCE_USERNAME=
SPRING_DATASOURCE_PASSWORD=

# ----- Authentication (shared JWT) ----------------------------------------- #
# Every service uses the same secret + algorithm so a token issued by one
# service is accepted by the others. Rotate the secret in production.
JWT_SECRET=change-me-32-bytes-of-random-data
JWT_ALGORITHM=HS256
JWT_ISSUER=devskel
JWT_ACCESS_TTL=3600
JWT_REFRESH_TTL=604800

# Django-specific salt. Falls back to JWT_SECRET when unset.
DJANGO_SECRET_KEY=

# ----- Per-service ports / hosts (override as needed) ---------------------- #
SERVICE_HOST=${SERVICE_HOST:-127.0.0.1}
SERVICE_PORT=${SERVICE_PORT:-8000}

# ----- Default backend URL ------------------------------------------------- #
# The frontend(s) in this wrapper read BACKEND_URL to know which backend
# they should call. Defaults to the django-bolt convention of
# http://localhost:8000 — point it at any other backend service in the
# wrapper by changing the value here (or by setting BACKEND_URL to a
# different SERVICE_URL_<SLUG> value from _shared/service-urls.env).
# The React skeleton's `src/api/items.ts` and `src/state/state-api.ts`
# both compose endpoints as \`\${BACKEND_URL}/api/...\`.
BACKEND_URL=http://localhost:8000

# Observability — structured logging + OpenTelemetry.
# LOG_FORMAT controls log output: "json" for structured JSON (prod),
# "console" for human-readable (dev, default).
LOG_FORMAT=console

# OpenTelemetry — uncomment and set OTEL_EXPORTER_OTLP_ENDPOINT to
# enable distributed tracing. Every backend that ships OTel wiring
# reads these vars.
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# OTEL_SERVICE_NAME=\${SERVICE_NAME:-devskel}

# ----- AI / Ollama --------------------------------------------------------- #
# Used by ./ai, ./backport, and skel-gen-ai for LLM-driven code generation.
# OLLAMA_HOST is the primary knob (host:port). The AI runtime derives the
# full URL automatically. Set OLLAMA_BASE_URL only if you need a custom
# scheme or path (it takes precedence over OLLAMA_HOST when set).
# OLLAMA_HOST=localhost:11434
# OLLAMA_MODEL=qwen3-coder:30b

# ----- Default accounts (seeded on first startup) ------------------------- #
# Every backend creates these accounts at startup if they don't exist.
# Change passwords before deploying to production.
USER_LOGIN=user
USER_EMAIL=user@example.com
USER_PASSWORD=secret
SUPERUSER_LOGIN=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=secret
EOF

if [[ ! -f "$MAIN_DIR/.env" ]]; then
  cp "$MAIN_DIR/.env.example" "$MAIN_DIR/.env"
  echo "  + .env (seeded from .env.example)"
fi

# When the caller (cross-stack integration runner, CI script, manual
# `SKEL_BACKEND_URL=... make gen-...` invocation) exports a custom
# `SKEL_BACKEND_URL`, propagate it into the wrapper-shared `.env` so
# every frontend in the wrapper picks it up at gen time. This is the
# "out of the box" wiring guarantee — without this hook, callers had
# to either accept the default `http://localhost:8000` or hand-edit
# `.env` AFTER generation (which broke pre-built artifacts).
#
# Idempotent: a re-run of common-wrapper.sh from the next service
# generated into the same wrapper sees the existing `.env` and rewrites
# only the BACKEND_URL line (or appends one if missing).
if [[ -n "${SKEL_BACKEND_URL:-}" ]]; then
  if grep -q '^BACKEND_URL=' "$MAIN_DIR/.env"; then
    # GNU sed wants `-i ''`-less syntax, BSD sed wants `-i ''`. Using
    # the `.bak` form works on both because we delete the backup right
    # after.
    sed -i.bak -E "s|^BACKEND_URL=.*|BACKEND_URL=${SKEL_BACKEND_URL}|" "$MAIN_DIR/.env"
    rm -f "$MAIN_DIR/.env.bak"
  else
    printf '\nBACKEND_URL=%s\n' "${SKEL_BACKEND_URL}" >> "$MAIN_DIR/.env"
  fi
  echo "  ↻ BACKEND_URL=${SKEL_BACKEND_URL} (from SKEL_BACKEND_URL)"
fi

# Touch the shared SQLite file so services do not need to create it on
# first run (still works for postgres because backends ignore the file when
# DATABASE_URL points elsewhere).
: >"$MAIN_DIR/_shared/db.sqlite3"

cat >"$MAIN_DIR/_shared/README.md" <<EOF
# _shared

This directory holds resources every service in **$PROJECT_TITLE** can rely
on:

- \`db.sqlite3\` — the default shared SQLite database. Backend services
  point at it via the \`DATABASE_URL\` environment variable defined in
  \`../.env\`. Swap \`DATABASE_URL\` for a \`postgresql://\` URL to switch
  to Postgres without touching service code.
- \`postgres-data/\` — bind-mount target used by \`../docker-compose.yml\`
  to persist Postgres state across container restarts.

The shared environment lives in \`../.env\` (gitignored) and \`../.env.example\`
(committed). Every wrapper script (\`./run\`, \`./test\`, \`./build\`,
\`./install-deps\`, ...) sources \`../.env\` before delegating to the inner
service script, so child processes inherit the same \`DATABASE_URL\`,
\`JWT_SECRET\`, etc.

Add helpers that should be available to every service here (shared SQL
schemas, message bus configs, OpenAPI bundles, etc.). Anything in
\`_shared\` is **never** modified by skeleton generators.
EOF

# Bind-mount target for the docker-compose Postgres service. Empty until
# the container writes its first datafile; tracked here so the path
# exists for shell completion and IDE indexing.
mkdir -p "$MAIN_DIR/_shared/postgres-data"

# --------------------------------------------------------------------------- #
#  1.5) docker-compose.yml — Postgres backing service
# --------------------------------------------------------------------------- #
#
# Idempotent: only written on the first run so the user can customise it
# without having `common-wrapper.sh` clobber edits on later regenerations.

# --------------------------------------------------------------------------- #
#  1.4) Per-service URL discovery
# --------------------------------------------------------------------------- #
#
# Maintains `_shared/service-urls.env` — a small file that maps every
# service slug in the wrapper to a `SERVICE_URL_<SLUG>` environment
# variable. The file is regenerated on every common-wrapper.sh run so
# adding or renaming a service automatically refreshes the cross-service
# URLs without touching the user-owned `.env`.
#
# Port allocation: services are sorted alphabetically by slug and
# assigned sequential ports starting at SERVICE_PORT_BASE (default 8000).
# When a service was already known on a previous run we preserve its
# port to keep the URLs stable across regenerations.

service_urls_file="$MAIN_DIR/_shared/service-urls.env"
service_url_host="${SERVICE_HOST:-127.0.0.1}"
service_url_base_port="${SERVICE_PORT_BASE:-8000}"

shopt -s nullglob
declare -a known_services=()
for dir in "$MAIN_DIR"/*/; do
  svc_name="$(basename "$dir")"
  case "$svc_name" in _shared|.*) continue ;; esac
  if [[ -x "${dir%/}/install-deps" ]]; then
    known_services+=("$svc_name")
  fi
done

# Preserve existing port assignments so URLs stay stable when a new
# service is added later. We re-read the previous service-urls.env file
# and look up each known service before assigning fresh ports for any
# newcomers.
declare -A existing_ports=()
if [[ -f "$service_urls_file" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in
      SERVICE_URL_*)
        slug="${key#SERVICE_URL_}"
        port="${value##*:}"
        existing_ports["$slug"]="$port"
        ;;
    esac
  done <"$service_urls_file"
fi

{
  printf '# Auto-generated by _skels/_common/common-wrapper.sh — DO NOT EDIT.\n'
  printf '# Sourced by every wrapper script alongside `.env` so service-to-\n'
  printf '# service URLs are available to handlers as SERVICE_URL_<SLUG>.\n'
  printf '#\n'
  printf '# Override the host or starting port via SERVICE_HOST / SERVICE_PORT_BASE\n'
  printf '# in `.env` and re-run any wrapper script to refresh.\n\n'
  next_port="$service_url_base_port"
  if [[ ${#known_services[@]} -eq 0 ]]; then
    printf '# (no services discovered yet)\n'
  else
    # Allocate ports in two passes: first reuse existing assignments,
    # then assign sequentially-allocated ports to any newcomer slug.
    declare -A allocated=()
    declare -a sorted_services=()
    while IFS= read -r line; do sorted_services+=("$line"); done < <(printf '%s\n' "${known_services[@]}" | LC_ALL=C sort)

    for svc in "${sorted_services[@]}"; do
      upper="$(printf '%s' "$svc" | LC_ALL=C tr '[:lower:]' '[:upper:]' | tr '-' '_')"
      if [[ -n "${existing_ports[$upper]:-}" ]]; then
        allocated["$upper"]="${existing_ports[$upper]}"
      fi
    done

    for svc in "${sorted_services[@]}"; do
      upper="$(printf '%s' "$svc" | LC_ALL=C tr '[:lower:]' '[:upper:]' | tr '-' '_')"
      if [[ -z "${allocated[$upper]:-}" ]]; then
        # Skip past any port already allocated to a different service.
        while :; do
          collision=0
          for assigned in "${allocated[@]}"; do
            if [[ "$assigned" == "$next_port" ]]; then
              collision=1
              break
            fi
          done
          [[ $collision -eq 0 ]] && break
          next_port=$((next_port + 1))
        done
        allocated["$upper"]="$next_port"
        next_port=$((next_port + 1))
      fi
    done

    for svc in "${sorted_services[@]}"; do
      upper="$(printf '%s' "$svc" | LC_ALL=C tr '[:lower:]' '[:upper:]' | tr '-' '_')"
      port="${allocated[$upper]}"
      printf 'SERVICE_URL_%s=http://%s:%s\n' "$upper" "$service_url_host" "$port"
      printf 'SERVICE_PORT_%s=%s\n' "$upper" "$port"
    done
  fi
} >"$service_urls_file"

echo "  + _shared/service-urls.env (${#known_services[@]} service(s))"

# Export the canonical OpenAPI contract spec into the wrapper so it
# ships alongside the generated services. Idempotent — always
# overwrites to keep the spec current with the dev_skel version.
OPENAPI_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openapi/wrapper-api.yaml"
if [[ -f "$OPENAPI_SRC" ]]; then
  mkdir -p "$MAIN_DIR/contracts/openapi"
  cp "$OPENAPI_SRC" "$MAIN_DIR/contracts/openapi/wrapper-api.yaml"
  echo "  + contracts/openapi/wrapper-api.yaml"
fi

if [[ ! -f "$MAIN_DIR/docker-compose.yml" ]]; then
  cat >"$MAIN_DIR/docker-compose.yml" <<'COMPOSE'
# Wrapper-level docker-compose for $PROJECT_TITLE.
#
# By default the wrapper uses the shared SQLite file at
# ./_shared/db.sqlite3 — no Docker required. To switch every service in
# the wrapper to Postgres without touching service code:
#
#   1) Bring up Postgres:        docker compose up postgres -d
#   2) Edit ./.env and set:      DATABASE_URL=postgresql://devskel:devskel@localhost:5432/devskel
#                                DATABASE_JDBC_URL=jdbc:postgresql://localhost:5432/devskel
#                                SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/devskel
#                                DATABASE_USER=devskel
#                                DATABASE_PASSWORD=devskel
#   3) ./install-deps && ./test  # every backend re-runs against Postgres
#
# Add additional service entries (one per dev_skel service in this
# wrapper) below as needed — they all inherit the same `.env` via the
# `env_file` directive.

services:
  postgres:
    image: postgres:16-alpine
    container_name: ${COMPOSE_PROJECT_NAME:-devskel}-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DATABASE_USER:-devskel}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:-devskel}
      POSTGRES_DB: ${DATABASE_NAME:-devskel}
    ports:
      - "${DATABASE_PORT:-5432}:5432"
    volumes:
      - ./_shared/postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DATABASE_USER:-devskel}"]
      interval: 5s
      timeout: 5s
      retries: 5

# Example: per-service entry. Uncomment and adapt as you add services.
#
#  ticket_service:
#    build: ./ticket_service
#    env_file:
#      - .env
#    depends_on:
#      postgres:
#        condition: service_healthy
#    ports:
#      - "${SERVICE_URL_TICKET_SERVICE_PORT:-8001}:8000"

# ── Observability profile ────────────────────────────────────
# Activate with: docker compose --profile observability up -d
# Then open http://localhost:3000 for Grafana (admin/admin).

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: \${COMPOSE_PROJECT_NAME:-devskel}-otel
    profiles: [observability]
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./_shared/otel-config.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP

  tempo:
    image: grafana/tempo:latest
    container_name: \${COMPOSE_PROJECT_NAME:-devskel}-tempo
    profiles: [observability]
    command: ["-config.file=/etc/tempo/tempo.yaml"]
    volumes:
      - ./_shared/tempo.yaml:/etc/tempo/tempo.yaml:ro
    ports:
      - "3200:3200"     # Tempo API

  grafana:
    image: grafana/grafana:latest
    container_name: \${COMPOSE_PROJECT_NAME:-devskel}-grafana
    profiles: [observability]
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
    ports:
      - "3000:3000"
    depends_on:
      - tempo
COMPOSE
  echo "  + docker-compose.yml (Postgres backing service)"
fi

# Append per-service entries to docker-compose.yml for the current service.
# Each backend that ships a Dockerfile gets a container entry so
# `docker compose up` boots the whole stack. Idempotent — skips if the
# service is already declared.
if [[ -n "$PROJECT_SUBDIR" ]] && \
   [[ -f "$MAIN_DIR/$PROJECT_SUBDIR/Dockerfile" ]] && \
   ! grep -q "^  ${PROJECT_SUBDIR}:" "$MAIN_DIR/docker-compose.yml" 2>/dev/null; then

  # Resolve the port. Gen scripts that bind to a non-8000 default
  # (next-js-skel binds 3000) export SERVICE_PORT before invoking
  # common-wrapper.sh; honor that first, fall back to the auto-
  # allocated value in service-urls.env, finally default to 8000.
  _UPPER=$(echo "$PROJECT_SUBDIR" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
  _PORT=""
  if [[ -n "${SERVICE_PORT:-}" ]]; then
    _PORT="${SERVICE_PORT}"
  elif [[ -f "$MAIN_DIR/_shared/service-urls.env" ]]; then
    _PORT=$(grep "^SERVICE_PORT_${_UPPER}=" "$MAIN_DIR/_shared/service-urls.env" 2>/dev/null | cut -d= -f2 || true)
  fi
  _PORT="${_PORT:-8000}"

  # Multi-stage Dockerfiles (the Python skels) ship a `production` stage
  # that bundles the source code; without `target: production`, docker
  # compose builds the LAST stage which is `development` and assumes a
  # bind-mount for code (k8s/wrapper compose has no such mount).
  if grep -q "^FROM .* AS production$" "$MAIN_DIR/$PROJECT_SUBDIR/Dockerfile" 2>/dev/null; then
    _BUILD_BLOCK=$'    build:\n      context: ./'"${PROJECT_SUBDIR}"$'\n      target: production'
  else
    _BUILD_BLOCK="    build: ./${PROJECT_SUBDIR}"
  fi

  cat >>"$MAIN_DIR/docker-compose.yml" <<SVCEOF

  ${PROJECT_SUBDIR}:
${_BUILD_BLOCK}
    container_name: \${COMPOSE_PROJECT_NAME:-devskel}-${PROJECT_SUBDIR}
    env_file:
      - .env
      - _shared/service-urls.env
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${_PORT}:${_PORT}"
SVCEOF
  echo "  + docker-compose.yml: added ${PROJECT_SUBDIR} service"
fi

# --------------------------------------------------------------------------- #
#  2) Wrapper README
# --------------------------------------------------------------------------- #

# Use a placeholder slug in the README examples when no service exists yet;
# the wrapper-only flow lays this README down before any service is added.
README_SVC_SLUG="${PROJECT_SUBDIR:-<service>}"

cat >"$MAIN_DIR/README.md" <<EOF
# $PROJECT_TITLE

Multi-service project wrapper generated by **dev_skel**. Each service lives
in its own subdirectory and shares a common environment (database, JWT
secret) via \`.env\` and \`_shared/\`.

## Layout

\`\`\`
./                          # this directory
├── .env                    # shared environment (DB URL, JWT secret, ...)
├── .env.example            # template for .env
├── _shared/                # shared resources (default sqlite, configs)
│   └── db.sqlite3          # default shared database
├── README.md / Makefile    # wrapper docs + convenience targets
├── run / test / build / stop / install-deps / services
│                           # multi-service dispatch scripts (see below)
└── <service>/              # one or more service directories
\`\`\`

## Wrapper scripts

Every wrapper script sources \`.env\` so the shared \`DATABASE_URL\`,
\`JWT_SECRET\`, and friends are available to the child process. Each
script accepts an optional first argument matching a service slug:

\`\`\`bash
./services                  # list every service the wrapper knows about
./run                       # run the first service (delegates to <svc>/run)
./run $README_SVC_SLUG dev   # run a specific service in dev mode
./test                      # run tests for every service that has ./test
./test $README_SVC_SLUG      # only run that service's tests
./build                     # build every service that has ./build
./install-deps              # install deps for every service
./stop                      # stop every running service
\`\`\`

Forwarded arguments after the optional service slug go straight to the
inner script — for example \`./run $README_SVC_SLUG dev --port=8001\`.

## Adding more services

Re-run the generator from the dev_skel root with another skeleton + service
name to add a second service to the same wrapper:

\`\`\`bash
make gen-fastapi NAME=$(basename "$MAIN_DIR") SERVICE="Auth Service"
make gen-django-bolt NAME=$(basename "$MAIN_DIR") SERVICE="Ticket Service"
\`\`\`

The wrapper scripts and Makefile auto-discover the new service the next
time they run; the shared \`.env\` is preserved.

See \`$README_SVC_SLUG/README.md\` for stack-specific details on the first
service.
EOF

# --------------------------------------------------------------------------- #
#  3) Wrapper Makefile (delegates to wrapper scripts)
# --------------------------------------------------------------------------- #

cat >"$MAIN_DIR/Makefile" <<'EOF'
.PHONY: help run test build stop lint format deps install-deps services

help:
	@echo "Multi-service wrapper targets:"
	@echo "  make services       - list services in this wrapper"
	@echo "  make run [SERVICE=] - run a service (default: first service)"
	@echo "  make test [SERVICE=]- run tests (default: every service)"
	@echo "  make build          - build every service"
	@echo "  make stop           - stop every service"
	@echo "  make install-deps   - install deps for every service"
	@echo "  make lint / format  - delegate to per-service ./lint / ./format"

services:
	./services

run:
	./run $(SERVICE)

test:
	./test $(SERVICE)

build:
	./build $(SERVICE)

stop:
	./stop $(SERVICE)

lint:
	./lint $(SERVICE)

format:
	./format $(SERVICE)

deps:
	./deps $(SERVICE)

install-deps:
	./install-deps $(SERVICE)
EOF

# --------------------------------------------------------------------------- #
#  4) ./services discovery script
# --------------------------------------------------------------------------- #

cat >"$MAIN_DIR/services" <<'SERVICES_SCRIPT'
#!/usr/bin/env bash
# Service discovery and management for this dev_skel wrapper.
#
# Usage:
#   ./services              # list all service slugs (default)
#   ./services list         # same
#   ./services info <slug>  # show details from dev_skel.project.yml
#   ./services set-active <slug>  # set the default for single-shot scripts

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_YML="$SCRIPT_DIR/dev_skel.project.yml"
ACTIVE_FILE="$SCRIPT_DIR/_shared/active-service"

_list_services() {
  shopt -s nullglob
  local found=0
  for dir in "$SCRIPT_DIR"/*/; do
    local name
    name="$(basename "$dir")"
    case "$name" in _shared|.*|contracts) continue ;; esac
    if [[ -x "${dir%/}/install-deps" ]]; then
      found=1
      echo "$name"
    fi
  done
  if [[ $found -eq 0 ]]; then
    echo "(no services found)" >&2
  fi
}

_info() {
  local slug="${1:-}"
  if [[ -z "$slug" ]]; then
    echo "Usage: ./services info <slug>" >&2
    return 1
  fi
  if [[ ! -f "$PROJECT_YML" ]]; then
    echo "No dev_skel.project.yml found — run any gen script first." >&2
    return 1
  fi
  # Simple grep-based extraction from the YAML
  local in_entry=0
  while IFS= read -r line; do
    if [[ "$line" == "  - id: $slug" ]]; then
      in_entry=1
      echo "$line"
    elif [[ $in_entry -eq 1 ]]; then
      if [[ "$line" =~ ^"  - id:" ]] || [[ "$line" =~ ^[a-z] ]]; then
        break
      fi
      echo "$line"
    fi
  done < "$PROJECT_YML"
  if [[ $in_entry -eq 0 ]]; then
    echo "Service '$slug' not found in dev_skel.project.yml" >&2
    return 1
  fi
}

_set_active() {
  local slug="${1:-}"
  if [[ -z "$slug" ]]; then
    echo "Usage: ./services set-active <slug>" >&2
    return 1
  fi
  if [[ ! -d "$SCRIPT_DIR/$slug" ]]; then
    echo "Service directory '$slug' does not exist." >&2
    return 1
  fi
  mkdir -p "$SCRIPT_DIR/_shared"
  echo "$slug" > "$ACTIVE_FILE"
  echo "Active service set to: $slug"
}

CMD="${1:-list}"
shift 2>/dev/null || true

case "$CMD" in
  list)       _list_services ;;
  info)       _info "$@" ;;
  set-active) _set_active "$@" ;;
  -h|--help)
    echo "Usage: ./services [list|info <slug>|set-active <slug>]"
    ;;
  *)
    # If the first arg looks like a slug (not a subcommand), treat
    # as shorthand for "info"
    _info "$CMD"
    ;;
esac
SERVICES_SCRIPT
chmod +x "$MAIN_DIR/services"

# --------------------------------------------------------------------------- #
#  5) Multi-service dispatch wrapper scripts
# --------------------------------------------------------------------------- #
#
# We pre-write the wrapper scripts here using a single template. Each script
# discovers services dynamically at runtime (so adding a new service does
# NOT require re-running common-wrapper.sh) and dispatches based on:
#
#   - The first positional argument matches a service slug → run only that
#     service's <script>.
#   - Otherwise the script is run on either the first service ("single-shot"
#     scripts like `run`) or every service that ships it ("fan-out" scripts
#     like `test`, `install-deps`, `build`, `stop`).

# Single-shot scripts: default to the first matching service.
SINGLE_SHOT_SCRIPTS=(run run-dev lint format deps)

# Fan-out scripts: default to every matching service.
#
# `ai` and `backport` sit in this list so that a bare wrapper-level
# invocation (`./ai "REQUEST"` or `./ai upgrade`) fans out across
# every service by default — the user can still scope to one service
# with `./ai <svc> "REQUEST"`. This matches the user's mental model:
# "at the project level, talk to the whole project; at the service
# level, talk to just this service".
FAN_OUT_SCRIPTS=(test build build-dev stop stop-dev install-deps ai backport)

write_dispatch_script() {
  local name="$1"
  local mode="$2"  # "single" | "fanout"
  local path="$MAIN_DIR/$name"

  cat >"$path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"

# Source the shared wrapper-level environment so every service inherits
# DATABASE_URL, JWT_SECRET, and friends without per-service duplication.
if [[ -f "\$SCRIPT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "\$SCRIPT_DIR/.env"
  set +a
fi
# Source the auto-generated service URL map so each handler can reach
# its sibling services via SERVICE_URL_<UPPER_SLUG>.
if [[ -f "\$SCRIPT_DIR/_shared/service-urls.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "\$SCRIPT_DIR/_shared/service-urls.env"
  set +a
fi

# Discover services that have this script.
shopt -s nullglob
SERVICES=()
for dir in "\$SCRIPT_DIR"/*/; do
  svc_name="\$(basename "\$dir")"
  case "\$svc_name" in _shared|.*) continue ;; esac
  if [[ -x "\${dir%/}/$name" ]]; then
    SERVICES+=("\$svc_name")
  fi
done

if [[ \${#SERVICES[@]} -eq 0 ]]; then
  echo "[$name] no service in this wrapper provides ./$name" >&2
  exit 0
fi

# --all forces fan-out: run the script on every service in the
# wrapper. Useful for ./ai --all "rename Item to Task" so a single
# request lands across the whole project (multi-service refactor).
# Recognised both as the first arg and embedded later in the arg list.
ALL_MODE=0
ARGS=()
for arg in "\$@"; do
  if [[ "\$arg" == "--all" ]]; then
    ALL_MODE=1
  else
    ARGS+=("\$arg")
  fi
done
set -- "\${ARGS[@]}"

# If the first arg matches a service slug, dispatch to that service only.
TARGET=""
if [[ \${#@} -gt 0 ]]; then
  for svc in "\${SERVICES[@]}"; do
    if [[ "\$1" == "\$svc" ]]; then
      TARGET="\$svc"
      shift
      break
    fi
  done
fi

run_one() {
  local svc="\$1"; shift
  echo "[$name] >>> \$svc"
  exec_cmd=("\$SCRIPT_DIR/\$svc/$name" "\$@")
  ( cd "\$SCRIPT_DIR/\$svc" && "\${exec_cmd[@]}" )
}

if [[ -n "\$TARGET" ]]; then
  run_one "\$TARGET" "\$@"
  exit \$?
fi

# --all promotes a "single" script into fan-out for this invocation
# (e.g. \`./ai --all "REQUEST"\` runs the AI request against every
# service that ships ./ai). Failures are accumulated like a fanout
# script; the final exit code is the last non-zero status.
if [[ "\$ALL_MODE" == 1 ]]; then
  status=0
  for svc in "\${SERVICES[@]}"; do
    run_one "\$svc" "\$@" || {
      rc=\$?
      status=\$rc
      echo "[\$svc] failed with exit \$rc" >&2
    }
  done
  exit \$status
fi

EOF

  if [[ "$mode" == "single" ]]; then
    cat >>"$path" <<'EOF'
# Default for single-shot scripts: pick the first service that has it.
run_one "${SERVICES[0]}" "$@"
EOF
  else
    cat >>"$path" <<'EOF'
# Default for fan-out scripts: run on every matching service in order.
# Capturing the exit code from the failing command requires the
# `cmd || { rc=$?; ... }` pattern — using `if ! cmd; then rc=$?` would
# capture the exit code of the negation (always 0), silently swallowing
# real failures and reporting "[svc] failed with exit 0".
status=0
for svc in "${SERVICES[@]}"; do
  run_one "$svc" "$@" || {
    rc=$?
    status=$rc
    echo "[$svc] failed with exit $rc" >&2
  }
done
exit $status
EOF
  fi

  chmod +x "$path"
  echo "  + $name (${mode})"
}

# Install the wrapper-shared `./ai` script + vendored runtime into
# every discovered service. The script is identical across skels;
# the per-service `./test` command embeds in `.skel_context.json`
# (or falls back to `./test` automatically) so each language picks
# up its own test runner.
COMMON_DIR_ABS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_INSTALLER="$COMMON_DIR_ABS/refactor_runtime/install-ai-script"
if [[ -x "$AI_INSTALLER" ]]; then
  shopt -s nullglob
  for dir in "$MAIN_DIR"/*/; do
    svc_name="$(basename "$dir")"
    case "$svc_name" in _shared|.*) continue ;; esac
    # Only services that ship at least one executable script (the
    # canonical "this is a real service dir" marker) get the AI
    # script; pure asset directories are left alone.
    has_script=0
    for f in "${dir%/}"/*; do
      [[ -f "$f" && -x "$f" ]] && { has_script=1; break; }
    done
    if [[ "$has_script" == 1 ]]; then
      # The just-generated service (PROJECT_SUBDIR) gets a
      # force-overwritten `.skel_context.json` so its sidecar always
      # matches the current gen invocation. Sibling services keep
      # their existing sidecars (each one was set when ITS gen ran).
      # SKEL_NAME is exported by the per-skel gen scripts before they
      # call common-wrapper.sh.
      if [[ "$svc_name" == "$PROJECT_SUBDIR" && -n "${SKEL_NAME:-}" ]]; then
        bash "$AI_INSTALLER" "${dir%/}" "$SKEL_NAME" force >/dev/null
      else
        bash "$AI_INSTALLER" "${dir%/}" >/dev/null
      fi
    fi
  done
fi

echo "[common-wrapper] Creating dispatch scripts..."

# Only create wrappers for scripts that actually exist in some service.
mapfile -t EXISTING_SERVICE_SCRIPTS < <(
  shopt -s nullglob
  for dir in "$MAIN_DIR"/*/; do
    svc_name="$(basename "$dir")"
    case "$svc_name" in _shared|.*) continue ;; esac
    for src in "${dir%/}"/*; do
      f="$(basename "$src")"
      [[ "$f" == *.* ]] && continue
      [[ -f "$src" && -x "$src" ]] || continue
      echo "$f"
    done
  done | sort -u
)

for name in "${EXISTING_SERVICE_SCRIPTS[@]}"; do
  mode="single"
  for n in "${FAN_OUT_SCRIPTS[@]}"; do
    if [[ "$n" == "$name" ]]; then
      mode="fanout"
      break
    fi
  done
  write_dispatch_script "$name" "$mode"
done

# --------------------------------------------------------------------------- #
#  7) Generate dev_skel.project.yml (AFTER the AI installer so sidecars exist)
# --------------------------------------------------------------------------- #

{
  KUBE_CLUSTER_NAME="${KUBE_CLUSTER_NAME:-${K8S_CLUSTER_NAME:-local}}"
  KUBE_CONTEXT="${KUBE_CONTEXT:-${K8S_CONTEXT:-default}}"
  KUBE_NAMESPACE="${KUBE_NAMESPACE:-${K8S_NAMESPACE:-swarm}}"
  IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-${KUBE_IMAGE_REPOSITORY:-${SWARM_REGISTRY:-beret}}}"

  echo "# Auto-generated by common-wrapper.sh — do not edit by hand."
  echo "# Re-run any gen script to refresh after adding/removing services."
  echo ""
  echo "project:"
  echo "  name: $(basename "$MAIN_DIR")"
  echo ""
  echo "kubernetes:"
  echo "  cluster: $KUBE_CLUSTER_NAME"
  echo "  context: $KUBE_CONTEXT"
  echo "  namespace: $KUBE_NAMESPACE"
  echo ""
  echo "images:"
  echo "  repository: $IMAGE_REPOSITORY"
  echo ""
  echo "services:"

  shopt -s nullglob
  for dir in "$MAIN_DIR"/*/; do
    svc_name="$(basename "$dir")"
    case "$svc_name" in _shared|.*|contracts) continue ;; esac

    sidecar="${dir%/}/.skel_context.json"
    skel_name=""
    skel_version=""
    if [[ -f "$sidecar" ]]; then
      skel_name=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('skeleton_name',''))" "$sidecar" 2>/dev/null || true)
      skel_version=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('skeleton_version',''))" "$sidecar" 2>/dev/null || true)
    fi

    kind="backend"
    case "$skel_name" in
      ts-react-skel|flutter-skel) kind="frontend" ;;
    esac

    upper=$(echo "$svc_name" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
    port=""
    if [[ -f "$MAIN_DIR/_shared/service-urls.env" ]]; then
      port=$(grep "^SERVICE_PORT_${upper}=" "$MAIN_DIR/_shared/service-urls.env" 2>/dev/null | cut -d= -f2 || true)
    fi

    echo "  - id: $svc_name"
    echo "    kind: $kind"
    [[ -n "$skel_name" ]] && echo "    tech: $skel_name"
    [[ -n "$skel_version" ]] && echo "    version: $skel_version"
    [[ -n "$port" ]] && echo "    port: $port"
    echo "    directory: ./$svc_name"
  done
} >"$MAIN_DIR/dev_skel.project.yml"
echo "  + dev_skel.project.yml"

# --------------------------------------------------------------------------- #
#  8) run-dev-all / stop-dev-all — multi-service launcher
# --------------------------------------------------------------------------- #

cat >"$MAIN_DIR/run-dev-all" <<'RUN_DEV_ALL'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Source shared env
if [[ -f "$SCRIPT_DIR/.env" ]]; then set -a; source "$SCRIPT_DIR/.env"; set +a; fi
if [[ -f "$SCRIPT_DIR/_shared/service-urls.env" ]]; then set -a; source "$SCRIPT_DIR/_shared/service-urls.env"; set +a; fi

# Discover services with ./run-dev
shopt -s nullglob
SERVICES=()
for dir in "$SCRIPT_DIR"/*/; do
  svc="$(basename "$dir")"
  case "$svc" in _shared|.*|contracts) continue ;; esac
  [[ -x "${dir%/}/run-dev" ]] && SERVICES+=("$svc")
done

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  echo "[run-dev-all] no services found with ./run-dev" >&2
  exit 0
fi

mkdir -p "$SCRIPT_DIR/_shared/logs"
PID_FILE="$SCRIPT_DIR/_shared/run-dev-all.pids"
> "$PID_FILE"

echo "[run-dev-all] Starting ${#SERVICES[@]} service(s)..."

for svc in "${SERVICES[@]}"; do
  log="$SCRIPT_DIR/_shared/logs/${svc}.log"
  echo "[run-dev-all] >>> $svc (log: _shared/logs/${svc}.log)"
  ( cd "$SCRIPT_DIR/$svc" && ./run-dev > "$log" 2>&1 ) &
  echo "$! $svc" >> "$PID_FILE"
done

echo ""
echo "[run-dev-all] All services started. PIDs in _shared/run-dev-all.pids"
echo "[run-dev-all] Tailing logs (Ctrl+C to stop)..."
echo ""

trap 'echo ""; echo "[run-dev-all] Stopping..."; bash "$SCRIPT_DIR/stop-dev-all"; exit 0' INT TERM
tail -F "$SCRIPT_DIR"/_shared/logs/*.log 2>/dev/null || wait
RUN_DEV_ALL
chmod +x "$MAIN_DIR/run-dev-all"

cat >"$MAIN_DIR/stop-dev-all" <<'STOP_DEV_ALL'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/_shared/run-dev-all.pids"

if [[ ! -f "$PID_FILE" ]]; then
  echo "[stop-dev-all] no PID file found — nothing to stop" >&2
  exit 0
fi

while read -r pid svc; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null && echo "[stop-dev-all] stopped $svc (pid $pid)"
  fi
done < "$PID_FILE"

rm -f "$PID_FILE"
echo "[stop-dev-all] all services stopped"
STOP_DEV_ALL
chmod +x "$MAIN_DIR/stop-dev-all"

# --------------------------------------------------------------------------- #
#  9) ./project + ./env — project-level UX helpers
# --------------------------------------------------------------------------- #

cat >"$MAIN_DIR/project" <<'PROJECT_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_YML="$SCRIPT_DIR/dev_skel.project.yml"
SERVICE_URLS="$SCRIPT_DIR/_shared/service-urls.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

_discover_services_with_script() {
  local script_name="$1"
  shopt -s nullglob
  for dir in "$SCRIPT_DIR"/*/; do
    local svc
    svc="$(basename "$dir")"
    case "$svc" in _shared|.*|contracts) continue ;; esac
    [[ -x "${dir%/}/$script_name" ]] && echo "$svc"
  done
}

_run_aggregated() {
  local script_name="$1"
  local total=0
  local ok=0
  local fail=0
  local -a lines=()

  mapfile -t services < <(_discover_services_with_script "$script_name")
  if [[ ${#services[@]} -eq 0 ]]; then
    echo "[project] no service in this wrapper provides ./$script_name" >&2
    exit 0
  fi

  for svc in "${services[@]}"; do
    total=$((total + 1))
    local started
    started="$(python3 - <<'PY'
import time
print(time.monotonic())
PY
)"
    local rc=0
    echo "[project] >>> $script_name $svc"
    if ! (cd "$SCRIPT_DIR/$svc" && "./$script_name"); then
      rc=$?
    fi
    local ended
    ended="$(python3 - <<'PY'
import time
print(time.monotonic())
PY
)"
    local elapsed
    elapsed="$(python3 - "$started" "$ended" <<'PY'
import sys
s=float(sys.argv[1]); e=float(sys.argv[2])
print(f"{max(0.0, e-s):.2f}s")
PY
)"

    if [[ $rc -eq 0 ]]; then
      ok=$((ok + 1))
      lines+=("${GREEN}✓${NC} ${svc} (${elapsed})")
    else
      fail=$((fail + 1))
      lines+=("${RED}✗${NC} ${svc} (${elapsed}) rc=${rc}")
    fi
  done

  echo ""
  echo -e "${BLUE}[project] ${script_name} summary${NC}"
  for line in "${lines[@]}"; do
    echo -e "  $line"
  done
  echo -e "${CYAN}[project] total=${total} ok=${ok} fail=${fail}${NC}"
  [[ $fail -eq 0 ]]
}

_emit_graph() {
  local format="${1:-mermaid}"
  if [[ ! -f "$PROJECT_YML" ]]; then
    echo "[project graph] missing dev_skel.project.yml" >&2
    return 1
  fi

  python3 - "$PROJECT_YML" "$SERVICE_URLS" "$format" <<'PY'
import re
import sys
from pathlib import Path

project_yml = Path(sys.argv[1])
service_urls = Path(sys.argv[2])
out_fmt = sys.argv[3]

services = []
edges = set()

for raw in project_yml.read_text(encoding="utf-8").splitlines():
    line = raw.rstrip()
    m = re.match(r"\s*-\s+id:\s+([a-zA-Z0-9_-]+)\s*$", line)
    if m:
        services.append(m.group(1))

known = set(services)
for env_file in [Path(".env"), Path(".env.example"), service_urls]:
    if not env_file.exists():
        continue
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "SERVICE_URL_" not in line:
            continue
        for target in known:
            token = "SERVICE_URL_" + target.upper().replace("-", "_")
            if token in line:
                lhs = line.split("=", 1)[0].strip()
                src = None
                m = re.match(r"^SERVICE_URL_([A-Z0-9_]+)$", lhs)
                if m:
                    maybe = m.group(1).lower().replace("_", "-")
                    if maybe in known:
                        src = maybe
                if src and src != target:
                    edges.add((src, target))

if out_fmt == "dot":
    print("digraph dev_skel {")
    print('  rankdir="LR";')
    for svc in services:
        print(f'  "{svc}";')
    for src, dst in sorted(edges):
        print(f'  "{src}" -> "{dst}";')
    print("}")
else:
    print("graph TD")
    for svc in services:
        print(f"  {svc}[{svc}]")
    for src, dst in sorted(edges):
        print(f"  {src} --> {dst}")
PY
}

_resolve_dev_skel_root() {
  if [[ -n "${DEV_SKEL_ROOT:-}" ]] && [[ -x "${DEV_SKEL_ROOT}/_bin/skel-deploy" ]]; then
    echo "$DEV_SKEL_ROOT"
    return 0
  fi
  local candidate
  for candidate in \
    "$HOME/dev_skel" \
    "$HOME/src/dev_skel" \
    "/opt/dev_skel" \
    "/usr/local/share/dev_skel"; do
    if [[ -x "$candidate/_bin/skel-deploy" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

cmd="${1:-}"
case "$cmd" in
  test|lint|build)
    shift
    _run_aggregated "$cmd"
    ;;
  graph)
    shift
    fmt="mermaid"
    if [[ "${1:-}" == "--dot" ]]; then
      fmt="dot"
    fi
    _emit_graph "$fmt"
    ;;
  kube)
    shift
    root="$(_resolve_dev_skel_root || true)"
    if [[ -z "$root" ]]; then
      echo "[project kube] ERROR: cannot find a dev_skel checkout." >&2
      echo "[project kube] Set DEV_SKEL_ROOT=<path>, or install dev_skel to" >&2
      echo "[project kube] one of: \$HOME/dev_skel, \$HOME/src/dev_skel," >&2
      echo "[project kube] /opt/dev_skel, /usr/local/share/dev_skel." >&2
      exit 1
    fi
    exec python3 "$root/_bin/skel-deploy" "$@" "$SCRIPT_DIR"
    ;;
  -h|--help|"")
    cat <<'EOF'
Usage: ./project <command>

Commands:
  test               Run ./test across all services with summary
  lint               Run ./lint across all services with summary
  build              Run ./build across all services with summary
  graph [--dot]      Emit service graph (Mermaid by default, DOT with --dot)
  kube <subcmd>      Forward to skel-deploy: bootstrap / sync / diff / e2e /
                     helm-gen / up / down / status
EOF
    ;;
  *)
    echo "[project] unknown command: $cmd" >&2
    echo "Use: ./project --help" >&2
    exit 1
    ;;
esac
PROJECT_SCRIPT
chmod +x "$MAIN_DIR/project"

cat >"$MAIN_DIR/env" <<'ENV_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

_profile_file() {
  local profile="$1"
  echo "$SCRIPT_DIR/.env.$profile"
}

_validate_profile() {
  case "$1" in
    dev|staging|prod) ;;
    *)
      echo "[env] unsupported profile '$1' (expected: dev|staging|prod)" >&2
      return 1
      ;;
  esac
}

cmd="${1:-}"
case "$cmd" in
  use)
    profile="${2:-}"
    _validate_profile "$profile"
    src="$(_profile_file "$profile")"
    if [[ ! -f "$src" ]]; then
      echo "[env] missing profile file: .env.$profile" >&2
      echo "[env] create it first (you can copy from .env.example)." >&2
      exit 1
    fi
    cp "$src" "$SCRIPT_DIR/.env"
    echo "$profile" > "$SCRIPT_DIR/_shared/active-env"
    echo "[env] active profile: $profile"
    ;;
  current)
    if [[ -f "$SCRIPT_DIR/_shared/active-env" ]]; then
      printf '%s\n' "$(cat "$SCRIPT_DIR/_shared/active-env")"
    else
      echo "default"
    fi
    ;;
  -h|--help|"")
    cat <<'EOF'
Usage:
  ./env use dev|staging|prod
  ./env current
EOF
    ;;
  *)
    echo "[env] unknown command: $cmd" >&2
    echo "Use: ./env --help" >&2
    exit 1
    ;;
esac
ENV_SCRIPT
chmod +x "$MAIN_DIR/env"

# --------------------------------------------------------------------------- #
# 10) ./deploy script — Kubernetes/Helm lifecycle
# --------------------------------------------------------------------------- #

cat >"$MAIN_DIR/kube" <<'DEPLOY_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
# Dev Skel deployment wrapper.
# Usage:
#   ./deploy helm-gen           # generate Helm chart from project metadata
#   ./deploy up                 # helm upgrade --install
#   ./deploy up -f deploy/helm/values-local.yaml  # with local overrides
#   ./deploy down               # helm uninstall
#   ./deploy status             # show release + pods

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find the dev_skel skel-deploy script
SKEL_DEPLOY=""
for candidate in \
  "$SCRIPT_DIR/../_bin/skel-deploy" \
  "${DEV_SKEL_ROOT:-}/bin/skel-deploy" \
  "$HOME/dev_skel/_bin/skel-deploy" \
  "$HOME/dev/_bin/skel-deploy"; do
  if [[ -x "$candidate" ]]; then
    SKEL_DEPLOY="$candidate"
    break
  fi
done

if [[ -z "$SKEL_DEPLOY" ]]; then
  echo "Error: skel-deploy not found. Set DEV_SKEL_ROOT or install dev_skel." >&2
  exit 1
fi

exec "$SKEL_DEPLOY" "${1:-helm-gen}" "$SCRIPT_DIR" "${@:2}"
DEPLOY_SCRIPT
chmod +x "$MAIN_DIR/kube"

echo "[common-wrapper] Done."
