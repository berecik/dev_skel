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
PROJECT_SUBDIR="${2:?project_subdir missing}"
PROJECT_TITLE="${3:-Generated Project}"

MAIN_DIR="$(cd "$MAIN_DIR" && pwd)"
PROJECT_DIR="$MAIN_DIR/$PROJECT_SUBDIR"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "[common-wrapper] ERROR: project dir '$PROJECT_DIR' does not exist" >&2
  exit 1
fi

echo "[common-wrapper] Preparing wrapper in: $MAIN_DIR (project: $PROJECT_SUBDIR)"
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
SERVICE_HOST=127.0.0.1
SERVICE_PORT=8000

# ----- Default backend URL ------------------------------------------------- #
# The frontend(s) in this wrapper read BACKEND_URL to know which backend
# they should call. Defaults to the django-bolt convention of
# http://localhost:8000 — point it at any other backend service in the
# wrapper by changing the value here (or by setting BACKEND_URL to a
# different SERVICE_URL_<SLUG> value from _shared/service-urls.env).
# The React skeleton's `src/api/items.ts` and `src/state/state-api.ts`
# both compose endpoints as \`\${BACKEND_URL}/api/...\`.
BACKEND_URL=http://localhost:8000
EOF

if [[ ! -f "$MAIN_DIR/.env" ]]; then
  cp "$MAIN_DIR/.env.example" "$MAIN_DIR/.env"
  echo "  + .env (seeded from .env.example)"
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
COMPOSE
  echo "  + docker-compose.yml (Postgres backing service)"
fi

# --------------------------------------------------------------------------- #
#  2) Wrapper README
# --------------------------------------------------------------------------- #

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
./run $PROJECT_SUBDIR dev   # run a specific service in dev mode
./test                      # run tests for every service that has ./test
./test $PROJECT_SUBDIR      # only run that service's tests
./build                     # build every service that has ./build
./install-deps              # install deps for every service
./stop                      # stop every running service
\`\`\`

Forwarded arguments after the optional service slug go straight to the
inner script — for example \`./run $PROJECT_SUBDIR dev --port=8001\`.

## Adding more services

Re-run the generator from the dev_skel root with another skeleton + service
name to add a second service to the same wrapper:

\`\`\`bash
make gen-fastapi NAME=$(basename "$MAIN_DIR") SERVICE="Auth Service"
make gen-django-bolt NAME=$(basename "$MAIN_DIR") SERVICE="Ticket Service"
\`\`\`

The wrapper scripts and Makefile auto-discover the new service the next
time they run; the shared \`.env\` is preserved.

See \`$PROJECT_SUBDIR/README.md\` for stack-specific details on the first
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

cat >"$MAIN_DIR/services" <<'EOF'
#!/usr/bin/env bash
# List every service directory in this wrapper.
#
# A service directory is any immediate subdirectory of the wrapper that
# contains an executable `install-deps` (the marker every dev_skel-generated
# service ships).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
shopt -s nullglob
found=0
for dir in "$SCRIPT_DIR"/*/; do
  name="$(basename "$dir")"
  case "$name" in _shared|.*) continue ;; esac
  if [[ -x "${dir%/}/install-deps" ]]; then
    found=1
    echo "$name"
  fi
done
if [[ $found -eq 0 ]]; then
  echo "(no services found in $SCRIPT_DIR)" >&2
fi
EOF
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
FAN_OUT_SCRIPTS=(test build build-dev stop stop-dev install-deps)

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

echo "[common-wrapper] Done."
