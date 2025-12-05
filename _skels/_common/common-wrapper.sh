#!/usr/bin/env bash
set -euo pipefail

# Common wrapper skeleton for generated projects.
#
# Usage:
#   common-wrapper.sh MAIN_DIR PROJECT_SUBDIR [PROJECT_TITLE]
#
# It assumes that the actual framework-specific project lives in
#   MAIN_DIR/PROJECT_SUBDIR
# and that project-level scripts (run, test, build, etc.) already exist there.
#
# The script will:
#   - Create/overwrite a generic README.md in MAIN_DIR.
#   - Create/overwrite a generic Makefile in MAIN_DIR.
#   - Create thin bash wrapper scripts in MAIN_DIR for each executable
#     script found directly under MAIN_DIR/PROJECT_SUBDIR (no extension),
#     forwarding all arguments.

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

mkdir -p "$MAIN_DIR"

# 1) Generic README for the wrapper directory
cat >"$MAIN_DIR/README.md" <<EOF
# $PROJECT_TITLE

This directory is a wrapper for a generated project located in \

  \
  ./$PROJECT_SUBDIR/\

The inner directory contains the actual framework-specific project
source code and configuration.

## Layout

\`$PROJECT_SUBDIR/\` – main project directory (source, config, tooling)
\`README.md\`      – this file (wrapper-level overview)
\`Makefile\`       – convenience targets that delegate to wrapper scripts
\`./<script>\`     – thin wrapper scripts that forward to \
\`$PROJECT_SUBDIR/<script>\`

## Usage

Run all commands from this wrapper directory. Wrapper scripts will forward
arguments to the inner project directory. For example:

\`\`\`bash
# Run development server (if inner project provides ./run)
./run dev

# Run tests (if inner project provides ./test)
./test

# Build artifacts or Docker image (if inner project provides ./build)
./build
\`\`\`

See the documentation inside \
\`$PROJECT_SUBDIR/README.md\` (if present) for stack-specific details.
EOF

# 2) Generic Makefile with common targets delegating to wrapper scripts
cat >"$MAIN_DIR/Makefile" <<'EOF'
.PHONY: help run test build stop lint format deps install-deps

help:
	@echo "Common targets:"
	@echo "  make run          - run application (delegates to ./run)"
	@echo "  make test         - run tests (delegates to ./test)"
	@echo "  make build        - build artifacts or image (delegates to ./build)"
	@echo "  make stop         - stop services (delegates to ./stop)"
	@echo "  make lint         - lint (delegates to ./lint)"
	@echo "  make format       - format code (delegates to ./format)"
	@echo "  make deps         - install system deps (delegates to ./deps)"
	@echo "  make install-deps - install project deps (delegates to ./install-deps)"

run:
	./run

test:
	./test

build:
	./build

stop:
	./stop

lint:
	./lint

format:
	./format

deps:
	./deps

install-deps:
	./install-deps
EOF

# 3) Create thin wrapper scripts for executable files in PROJECT_DIR root

echo "[common-wrapper] Creating wrapper scripts..."

shopt -s nullglob
for src in "$PROJECT_DIR"/*; do
  name="$(basename "$src")"

  # We only wrap regular executable files with no extension
  if [[ ! -f "$src" || ! -x "$src" ]]; then
    continue
  fi

  if [[ "$name" == *.* ]]; then
    continue
  fi

  wrapper="$MAIN_DIR/$name"
  cat >"$wrapper" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/__PROJECT_SUBDIR__"

exec "$PROJECT_DIR/__SCRIPT_NAME__" "$@"
EOF

  # Replace placeholders with actual values
  sed -i '' "s/__PROJECT_SUBDIR__/$PROJECT_SUBDIR/g" "$wrapper"
  sed -i '' "s/__SCRIPT_NAME__/$name/g" "$wrapper"

  chmod +x "$wrapper"
  echo "  + $name -> $PROJECT_SUBDIR/$name"
done

echo "[common-wrapper] Done."
