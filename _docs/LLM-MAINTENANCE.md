# LLM Maintenance Guide

Instructions for AI assistants (Claude, GPT, Gemini, etc.) maintaining this project.

## Project Overview

**Dev Skel generates whole multi-service projects where every service
ships with its own in-service code agent.** Three AI surfaces, each
with its own design doc, smokes, and operator commands:

1. **`_bin/skel-gen-ai`** (template → new project) — full-stack
   dialog that asks for backend + frontend separately, then runs five
   Ollama phases: per-target backend overlay → per-target frontend
   overlay → cross-service integration → bounded test-and-fix loop →
   per-service docs. Backed by `_bin/skel_rag/` (FAISS RAG agent)
   under the `_bin/skel_ai_lib.py` shim. Static AI-free fallback at
   `_bin/skel-gen-static`.
2. **`./ai`** (in-service code agent) — shipped in every generated
   service. Subcommands: `propose`, `apply`, `verify`, `explain`,
   `history`, `undo`, `upgrade`. Two activation modes: in-tree (full
   RAG via `skel_rag.agent.RagAgent`) and out-of-tree (stdlib-only
   retrieval + minimal fix loop). Wrapper-level `./ai` fans out
   across services by default.
3. **`./backport` + `./ai upgrade`** (service ↔ template sync) —
   `./backport apply` writes service edits upstream into the
   skeleton template AND bumps the skeleton's `VERSION` (semver
   patch) AND prepends a `## [VERSION] - DATE` entry to
   `<skel>/CHANGELOG.md` listing every backported file. `./ai
   upgrade` reads the sidecar's `skeleton_version`, compares against
   `<skel>/VERSION`, extracts the matching CHANGELOG entries, and
   synthesises an AI request that asks the model to apply those
   changes to the service.

The infrastructure piece — and most of the legacy docs — is the
**Makefile-based project generator**: a delegation pattern where the
main Makefile calls skeleton-specific Makefiles. Each skeleton ships a
`gen` script (full generation logic), a `merge` script (rsync
helper), a `test` script (e2e self-test), a `deps` script (toolchain
installer), a `VERSION`, and a `CHANGELOG.md`.

The relocatable CLI (`_bin/skel-gen`, `_bin/skel-install`,
`_bin/skel-update`, `_bin/skel-sync`, `_bin/skel-list`) is now a set
of small Python entrypoints sharing logic in `_bin/dev_skel_lib.py`. Treat
that module as the single source of truth for config loading, project
generation, rsync wrappers, and AGENTS template rendering. The legacy
`_bin/common.sh` is kept only for backwards compatibility — do not extend it.

LLM assistants (including Junie and Claude) have a small hierarchy of rules
documents:

1. Cross-agent baseline: `/AGENTS.md` (Claude Code reads `/CLAUDE.md`, which
   delegates to `/AGENTS.md`).
2. Global rules: `_docs/JUNIE-RULES.md`.
3. General maintenance guide: this file (`_docs/LLM-MAINTENANCE.md`).
4. Per-skeleton rules: `_skels/<name>/JUNIE-RULES.md` and
   `_skels/<name>/AGENTS.md` (or `CLAUDE.md` if present).
5. Per-skeleton docs under `_docs/` (for example `python-fastapi-skel.md`).

When maintaining this project, always read `/AGENTS.md` (or `/CLAUDE.md`),
`_docs/JUNIE-RULES.md`, and this file first, then load any skeleton-specific
rules file for the skeleton you are working on.

### Mandatory Rule: Where to Create Test Projects

- All assistants (Junie and other LLMs) must create any generated testing
  projects strictly under the `_test_projects/` directory. This includes
  ad-hoc debug apps, reproduction cases, and temporary scaffolds.
- Never place such projects at the repository root or inside `_skels/`,
  `_docs/`, or service/skeleton directories.

### Maintenance Scenario (What "do maintenance" Means)

For this repository, "do maintenance" or "maintenance task" has a specific
default workflow that all LLMs should follow unless the user explicitly
requests a different order:

1. **Run generator tests first**
   - From the project root, run:
     - `make clean-test`
     - `make test-generators`
   - This exercises all skeletons. If the user has requested maintenance for
     a single skeleton only, you may instead run just the focused tests for
     that skeleton as described later in this guide.

2. **Fix all reported issues until tests are green**
   - Investigate any failures reported by `make test-generators` or
     skeleton-specific tests.
   - Apply minimal, targeted fixes in the affected skeletons, scripts, or
     configuration files.
   - Re-run the same tests until **no issues remain**.

3. **Then maintain and update LLM rules/docs**
   - After tests are passing, review and update as needed:
     - Global rules: `_docs/JUNIE-RULES.md`.
     - This guide: `_docs/LLM-MAINTENANCE.md`.
     - Any relevant `_skels/<name>/JUNIE-RULES.md` files.
     - Per-skeleton docs under `_docs/`.
   - Ensure that any behavioural or workflow changes made while fixing tests
     are reflected in these documents.

4. **All skeletons vs. one skeleton**
   - If the user says "do maintenance for this project" or similar, assume
     they mean **all skeletons** and run the global test commands above.
   - If the user explicitly names a skeleton (for example, "maintain
     python-fastapi-skel"), you may restrict testing and rule/doc updates to
     that skeleton plus any global rules that must change as a result.

5. **Check CI after pushing** — `make ci-status` lists recent runs,
   `make ci-watch` tails the latest in real time, `make ci-log` dumps
   the full log. All three require `gh auth login` (one-time). The
   GitHub Actions workflow (`.github/workflows/maintenance.yml`) runs
   the same `./maintenance` triplet on every push / PR to `master`.

## Key Files to Understand

Before making changes, read these files:

1. **`Makefile`** - Main orchestration file
2. **`_skels/*/Makefile`** - Individual skeleton Makefiles (9 total)
3. **`_docs/MAKEFILE.md`** - Makefile architecture documentation
4. **`_docs/SKELETONS.md`** - Skeleton template details
5. **`_docs/DEPENDENCIES.md`** - Dependency management system documentation
6. **`_bin/dev_skel_lib.py`** - Shared Python helpers (config, generation,
   rsync, AGENTS template rendering) used by every `_bin/` CLI
7. **`_bin/skel_ai_lib.py`** - Ollama-backed AI generator library
   (`OllamaClient`, `GenerationContext`, manifest loader, prompt rendering,
   target writer). Stdlib only.
8. **`_bin/skel-gen`** - Canonical entrypoint. As of 2026-04 it is a
   thin dispatcher that exec's the AI generator by default
   (`_bin/skel-gen-ai`) or the static fallback when `--static` is
   passed (`_bin/skel-gen-static`). Positional order: `[proj_name]
   [skel_name] [service_name]` — both `proj_name` and `skel_name`
   are optional. `proj_name=.` (or omitted) installs into the current
   directory.
9. **`_bin/skel-add`** - Existing-wrapper sibling of `skel-gen`.
   Same positional order, but the wrapper must already exist. Default
   mode is AI: it exec's `_bin/skel-gen-ai --skip-base`, so the new
   service still runs through the per-target overlay, sibling-aware
   integration phase, test-and-fix loop, and docs generation. Passing
   `--static` dispatches to `_bin/skel-gen-static --existing-project`.
9. **`_bin/skel-gen-ai`** - Relocatable Ollama-augmented generator.
   Runs the static skel-gen first (unless `--skip-base`), then loads
   the AI manifest at `_skels/_common/manifests/<skel>.py` and rewrites
   the listed files via Ollama. Two modes: **single-skeleton** (when an
   explicit positional `skel_name` is given) and **full-stack** (when
   omitted — asks for backend + frontend + three custom prompts and
   integrates them). Same positional order as `skel-gen`. The
   `_bin/skel-gen-ai` name is preserved as a stable alias for scripts
   that want to pin the AI path explicitly.
10. **`_bin/skel-gen-static`** - Pre-2026-04 `skel-gen` content,
    renamed when the canonical entrypoint switched to AI by default.
    No Ollama involved — just the static skeleton overlay through
    `dev_skel_lib.generate_project()`. Use this in CI / when Ollama
    is unavailable / when you want a deterministic AI-free baseline.
    Same `[proj_name] [skel_name] [service_name]` positional order.
    `--existing-project` switches it into add-service mode for wrappers
    that already exist on disk.
10. **`_bin/skel-test-ai-generators`** - End-to-end test runner for the AI
    generator. Auto-discovers manifests under
    `_skels/_common/manifests/`, runs base scaffold + Ollama overlay for
    each, then validates the result with a per-skeleton sanity check.
    **All 10 skeletons** are wired in:
    - Django / Django-Bolt → `manage.py check` (+ `pytest --collect-only`
      for django-bolt).
    - FastAPI / Flask → module import via the production app factory.
    - Spring → `mvn -q -DskipTests package`.
    - Rust Actix / Axum → `cargo check --quiet`.
    - JS → `node --check` per file + ESM import smoke.
    - React → `npx tsc --noEmit`.
    - Flutter → `flutter pub get` + `flutter analyze`.
    Validators that need a missing toolchain (Maven, Cargo, Node,
    Flutter) skip silently; toolchains that *are* present run the
    full per-stack check. Backs the `make test-ai-generators` target.
    Opt-in (separate from `make test-generators`) because it needs
    Ollama and is slow.
11. **`_bin/skel-test-shared-db`** - Cross-language integration test runner.
    Generates a wrapper containing every backend skeleton, seeds the
    shared SQLite `items` table, and runs a per-stack verifier that
    confirms each backend reads the seed row through `DATABASE_URL`.
    Performs a cross-stack write/read round-trip across two Python
    venvs to prove data is genuinely shared (not just the file path).
    Skips toolchains that aren't installed (`java`, `cargo`, `node`)
    gracefully so it runs on minimal CI hosts. Backs the
    `make test-shared-db` family of targets.
12. **`_bin/_frontend_backend_lib.py`** - Shared helpers for the
    frontend + backend cross-stack integration tests. Defines:
    - `BackendSpec` (declarative description of a backend: skel name,
      service display name, server argv, optional pre-server setup).
    - `Frontend` (declarative description of a frontend: skel name,
      toolchain probe, build callable, build-output inspector,
      optional `frontend_smoke` callable).
    - `REACT_FRONTEND` and `FLUTTER_FRONTEND` instances ready to plug
      into the generic driver. Both ship a `frontend_smoke` that
      invokes the frontend's own test runner against the live
      backend (see step 9 below).
    - `run_frontend_backend_integration(frontend, spec, ...)` —
      generic 9-step driver: generate wrapper → set BACKEND_URL →
      build frontend → inspect bundle → run backend setup → start
      server → exercise items API via Python → run the FRONTEND
      smoke (vitest / flutter test against the real client code) →
      stop server → clean up. The HTTP pre-flight catches backend
      regressions fast; the frontend smoke catches client-side
      regressions in `src/api/items.ts` / `lib/api/items_client.dart`
      that a Python-only smoke would miss.
    - `_react_smoke(frontend_dir, backend_url)` — runs `npx vitest
      run src/cross-stack.smoke.test.ts` with `RUN_CROSS_STACK_SMOKE=1`
      and `BACKEND_URL=...`. The smoke file imports the real
      `loginWithPassword`, `listItems`, `createItem`, `getItem`,
      `completeItem`, and `AuthError` and runs the 9-step flow.
    - `_flutter_smoke(frontend_dir, backend_url)` — runs `flutter
      test test/cross_stack_smoke_test.dart` with the same env vars.
      The smoke file imports the real `ItemsClient`, `Item.fromJson`,
      `NewItem`, and `AuthError` and runs the 9-step flow.
      Bypasses `flutter_secure_storage` by setting
      `TokenStore.instance.value` directly (platform channels are
      unavailable under `flutter test`).
    - `run_react_backend_integration(...)` — backwards-compat shim
      that forwards to the generic driver with `REACT_FRONTEND`.
13. **`_bin/skel-test-react-django-bolt`,
    `_bin/skel-test-react-fastapi`, `_bin/skel-test-react-flask`,
    `_bin/skel-test-react-django`, `_bin/skel-test-react-spring`,
    `_bin/skel-test-react-actix`, `_bin/skel-test-react-axum`,
    `_bin/skel-test-react-go`, `_bin/skel-test-flutter-django-bolt`,
    `_bin/skel-test-flutter-fastapi`** - Per-(frontend, backend)
    cross-stack integration tests. Each is a ~150-line driver that
    builds a `BackendSpec` and forwards to
    `run_frontend_backend_integration`. The React tests verify the
    Vite-baked bundle (`dist/assets/*.js`); the Flutter tests verify
    the bundled `.env` asset (`build/web/assets/.env`) and the
    compiled `main.dart.js`. Every driver hits the canonical 9-step
    `register → login → CRUD → complete → reject` items API flow
    TWICE: once via Python pre-flight (cheap, fast feedback when the
    backend is broken) and once via the frontend's own client code
    (proves the frontend ↔ backend contract end-to-end). Backs
    the per-pair `make test-react-*` / `make test-flutter-*` targets,
    `make test-react-cross-stack` (the static React + backend matrix:
    django-bolt, fastapi, flask, django, spring, actix, axum, go),
    `make test-flutter-cross-stack` (currently the Flutter +
    django-bolt/fastapi matrix), and `make test-cross-stack` (the
    umbrella that runs the shared-db check, the full React matrix,
    then the full Flutter matrix).
14. **`_skels/ts-react-skel/src/cross-stack.smoke.test.ts` and
    `_skels/flutter-skel/test/cross_stack_smoke_test.dart`** -
    Frontend smoke tests shipped with each frontend skeleton. Both
    are gated on the `RUN_CROSS_STACK_SMOKE=1` environment variable,
    so a developer running `npm test` / `flutter test` against a
    fresh wrapper sees them skip cleanly. The cross-stack runner
    enables them by exporting the env var before invoking the
    frontend's test runner. Both files own a distinct test user
    (`react-smoke-user` / `flutter-smoke-user`) so they never
    collide with the Python pre-flight's `react-integration-user`.
16. **`_bin/skel-install` / `skel-update` / `skel-sync` /
    `skel-list`** - Other relocatable Python CLIs that share `dev_skel_lib.py`
17. **`_skels/_common/common-wrapper.sh`** - Wrapper-directory scaffolder used
    by all skeletons
18. **`_skels/_common/AGENTS.md`** - Templated agents file rendered into
    every generated project
19. **`_skels/_common/manifests/<skel>.py`** - Per-skeleton AI generation
    manifests consumed by `skel-gen-ai`. Each manifest exports a top-level
    `MANIFEST` dict listing the files to (re)generate, the template files
    they should reference, and the prompt for each.
20. **`skel-deps`** - Main dependency installer
21. **`_skels/*/deps`** - Per-skeleton dependency installers

## Common Tasks

### Task: Add a New Skeleton

1. **Create skeleton directory**:
   ```bash
   mkdir -p _skels/language-framework-skel/src
   ```

2. **Add skeleton source files** with working example code

3. **Create skeleton Makefile** (`_skels/language-framework-skel/Makefile`):
  - Must define `gen` and `test` targets and set `MERGE := $(SKEL_DIR)/merge`.
  - Call the merge script as: `bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"`.
  - The `test` target should delegate to `bash ./test`.

  Example skeleton Makefile snippet:
  ```makefile
  .PHONY: gen test
  SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
  MERGE := $(SKEL_DIR)/merge

  gen: ## Generate project (NAME=myapp)
  ifndef NAME
  	@echo "Usage: make gen NAME=<project-name>"
  	@exit 1
  endif
  	# ... framework-specific setup ...
  	@bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"
  	# ... post-setup steps ...

  test: ## Generate a temp project and run its tests (e2e)
  	@bash ./test
  ```

4. **Update main Makefile**:
   - Add variable: `NEW_SKEL := $(SKEL_DIR)/language-framework-skel`
   - Add to SKELETONS list
   - Add to .PHONY
   - Add `gen-new` target
   - Add `test-gen-new` target
   - Add `test-new` target

5. **Add helper scripts** in the skeleton directory:
   - `merge` (executable Bash): copy auxiliary files; exclude generator-owned files.
   - `gen` (executable Bash): wrapper that runs `make -C "$SKEL_DIR" gen NAME="$TARGET"`.
   - `test` (executable Bash): generates into a temp dir, runs tests, performs a non-interactive run/build check.

6. **Add dependency installers**:
   - **System deps** (`_skels/new-framework-skel/deps`): Installs framework tools (Node.js, Python, etc.)
     - Follow the deps script template (see "Task: Add or Update Dependency Scripts")
     - Make executable: `chmod +x _skels/new-framework-skel/deps`
     - Test on supported platforms

   - **Project deps** (`_skels/new-framework-skel/install-deps`): Installs project packages
     - This script is copied to generated projects
     - Installs npm packages, pip packages, Maven dependencies, etc.
     - Make executable: `chmod +x _skels/new-framework-skel/install-deps`
     - Should detect if tools are missing and give helpful error messages

7. **Test**: `make test-generators`

8. **Update documentation** in `_docs/SKELETONS.md` and `_docs/DEPENDENCIES.md`

---

### Task: Update Dependencies in a Skeleton

**For Python skeletons**:
- Update the pip install lines in the skeleton's Makefile `gen` target.
- Prefer Python 3.11+.
- Test with `make test-gen-<name>` and `make test-<name>`.

**For Node.js skeletons**:
- Update `package.json` in the skeleton when appropriate.
- Or update the `npm` commands in the skeleton Makefile.
- Test with `make test-gen-<name>` and `make test-<name>`.

**For Java skeletons**:
- Update `pom.xml` in the skeleton.
- Test with `make test-gen-spring` and `make test-spring`.

**For Rust skeletons**:
- Update `Cargo.toml` in the skeleton.
- Regenerate `Cargo.lock`: `cd _skels/rust-*-skel && cargo update`.
- Test with `make test-gen-<name>` and `make test-<name>`.

---

### Task: Fix Generator Bugs

**Debugging approach**:
1. Run the failing generator manually:
   ```bash
   make gen-<name> NAME=_test_projects/debug-app 2>&1 | tee debug.log
   ```

2. Check the skeleton Makefile and scripts for issues:
   - Path handling in `merge` script and its exclusions
   - Command sequences in `gen` target and pre/post steps
   - Test script behavior and non-interactive checks

3. Common issues:
   - **Path issues**: Ensure `SKEL_DIR` is resolved via `$(dir $(abspath $(lastword $(MAKEFILE_LIST))))`.
   - **File not copied**: Check exclusion patterns in the `merge` script.
   - **File overwritten**: `merge` must only copy when destination does not exist.
   - **Wrong directory**: Ensure commands use `$(NAME)` or absolute paths, not relative ones.

4. After fixing, run full test suite:
   ```bash
   make clean-test && make test-generators
   ```

---

### Task: Update Skeleton Source Code

1. **Modify files** in `_skels/<name>/`

2. **Important**: Don't modify:
   - `node_modules/`
   - `.venv/`
   - `target/`
   - Any build artifacts

3. **Test the generator**:
   ```bash
   make clean-test && make test-gen-<name>
   ```

4. **For ts-react-skel** specifically:
   - Do not overwrite generator-owned files: `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts` (see the skeleton `merge` script for exact rules).

---

### Task: Add or Update Dependency Scripts

The project includes a comprehensive dependency management system with per-skeleton `deps` scripts and a main `skel-deps` orchestrator.

#### Dependency System Architecture

**Main Components**:
1. **`skel-deps`** - Central dependency installer at project root
   - Auto-detects OS (macOS, Ubuntu/Debian, Arch Linux, Fedora/RHEL)
   - Lists all skeletons with dependency script status
   - Installs dependencies for all or specific skeletons
   - Provides unified interface and help

2. **`_skels/*/deps`** - Per-skeleton dependency installers
   - Bash scripts that install system dependencies for that framework
   - OS detection and platform-specific installation
   - Dependency verification after installation
   - Colored output for better UX

#### deps Script Template

Each skeleton should have a `deps` script following this pattern:

```bash
#!/usr/bin/env bash
# Dependency installer for <Framework Name> skeleton
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Detect OS
detect_os() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ -f /etc/os-release ]]; then
    . /etc/os-release
    case "$ID" in
      ubuntu|debian) echo "ubuntu" ;;
      arch|manjaro) echo "arch" ;;
      fedora|rhel|centos) echo "fedora" ;;
      *) echo "unknown" ;;
    esac
  else
    echo "unknown"
  fi
}

# Check if command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Install dependencies based on OS
install_deps() {
  local os="$1"

  info "Installing <Framework> dependencies for $os..."

  case "$os" in
    macos)
      if ! command_exists brew; then
        error "Homebrew is required but not installed. Visit https://brew.sh"
        exit 1
      fi
      info "Installing packages..."
      brew install package1 package2
      ;;

    ubuntu)
      info "Installing packages..."
      sudo apt-get update
      sudo apt-get install -y package1 package2
      ;;

    arch)
      info "Installing packages..."
      sudo pacman -S --needed --noconfirm package1 package2
      ;;

    fedora)
      info "Installing packages..."
      sudo dnf install -y package1 package2
      ;;

    *)
      error "Unsupported OS: $os"
      exit 1
      ;;
  esac
}

# Verify installation
verify_deps() {
  info "Verifying installations..."

  if command_exists tool1; then
    info "Tool1: $(tool1 --version)"
  else
    error "Tool1 not found"
    return 1
  fi

  info "All dependencies verified successfully!"
}

# Main
main() {
  local os
  os=$(detect_os)

  if [[ "$os" == "unknown" ]]; then
    error "Unable to detect OS"
    exit 1
  fi

  info "Detected OS: $os"
  install_deps "$os"
  verify_deps
}

main "$@"
```

#### Adding deps to a New Skeleton

When creating a new skeleton, add a `deps` script:

1. **Create the script**: `_skels/new-framework-skel/deps`
2. **Make it executable**: `chmod +x _skels/new-framework-skel/deps`
3. **Follow the template** above
4. **Define dependencies** in `install_deps()` for each OS
5. **Add verification** in `verify_deps()` to check installations
6. **Test on each supported platform** if possible

The `skel-deps` script will automatically detect the new `deps` script.

#### Current Skeleton Dependencies

**Java Spring** (`java-spring-skel/deps`):
- JDK (OpenJDK 21+)
- Maven

**JavaScript/Node.js** (`next-js-skel/deps`, `ts-react-skel/deps`):
- Node.js 20+
- npm

**Python** (`python-*-skel/deps`):
- Python 3.10+
- pip
- venv module

**Rust** (`rust-*-skel/deps`):
- Rust via rustup
- Build tools (platform-specific: build-essential, base-devel, etc.)
- OpenSSL development libraries

#### Updating Existing deps Scripts

**When to update**:
- Minimum version requirements change
- New OS support needed
- Package names change on a platform
- Additional tools required

**How to update**:
1. Edit the relevant `_skels/*/deps` script
2. Update version checks in `verify_deps()` if needed
3. Test on the target platform
4. Update `_docs/DEPENDENCIES.md` documentation

**Example - Updating minimum Node.js version**:
```bash
# In verify_deps() function
local node_version
node_version=$(node --version | sed 's/v//' | cut -d. -f1)
if [[ "$node_version" -lt 22 ]]; then  # Changed from 20 to 22
  warn "Node.js version is $node_version, but >= 22 is recommended"
fi
```

#### OS-Specific Considerations

**macOS**:
- Requires Homebrew pre-installed
- Check with `command_exists brew` and provide install URL if missing
- Some packages need Xcode Command Line Tools

**Ubuntu/Debian**:
- Always run `sudo apt-get update` before install
- Node.js from default repos may be old - warn users about NodeSource
- Python venv requires separate `python3-venv` package

**Arch Linux**:
- Use `--needed` to skip already-installed packages
- Use `--noconfirm` for non-interactive installation
- Python venv is included with Python package

**Fedora/RHEL**:
- Use `dnf` instead of older `yum`
- Development tools often in group: `dnf groupinstall "Development Tools"`
- Java package naming: `java-21-openjdk-devel` (note `-devel` suffix)

**Rust (All Platforms)**:
- Don't use system package managers
- Use rustup installer: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`
- Remind users to source `~/.cargo/env` or restart shell

#### Common Pitfalls to Avoid

1. **Don't use `((counter++))` with `set -e`**:
   ```bash
   # WRONG - exits when counter is 0
   ((counter++))

   # CORRECT
   counter=$((counter + 1))
   ```

2. **Don't assume sudo is available**:
   ```bash
   # Check if needed and provide clear error
   if ! command_exists sudo && [[ "$os" != "macos" ]]; then
     error "sudo is required for package installation"
     exit 1
   fi
   ```

3. **Don't hardcode package versions unless necessary**:
   ```bash
   # WRONG
   brew install node@20

   # BETTER - get latest LTS
   brew install node
   ```

4. **Always verify installations**:
   - Check that commands exist after installation
   - Show version information to user
   - Return error if verification fails

5. **Handle missing package managers gracefully**:
   - For macOS, check for Homebrew and provide install URL
   - For other systems, clear error message about unsupported OS

#### Testing deps Scripts

**Manual testing**:
```bash
# Test on your current system
cd _skels/java-spring-skel
./deps

# Test via main script
./skel-deps java-spring-skel

# Test listing
./skel-deps --list
```

**Integration testing**:
```bash
# Ensure all deps scripts are executable
ls -l _skels/*/deps

# Test that skel-deps detects all scripts
./skel-deps --list | grep -c "✓"  # Should equal number of skeletons
```

**Platform testing**:
- Test on each supported OS if possible
- Use Docker/VMs for other platforms
- At minimum, verify script syntax: `bash -n _skels/*/deps`

#### Updating skel-deps Main Script

The `skel-deps` script rarely needs updates, but if adding new OS support:

1. **Update `detect_os()` function**:
   ```bash
   detect_os() {
     # Add new OS detection
     if [[ -f /etc/os-release ]]; then
       . /etc/os-release
       case "$ID" in
         ubuntu|debian) echo "ubuntu" ;;
         arch|manjaro) echo "arch" ;;
         fedora|rhel|centos) echo "fedora" ;;
         opensuse*) echo "opensuse" ;;  # New OS
         *) echo "unknown" ;;
       esac
     fi
   }
   ```

2. **Update `get_os_name()` for display**:
   ```bash
   get_os_name() {
     local os="$1"
     case "$os" in
       # ... existing cases ...
       opensuse) echo "openSUSE" ;;  # New OS
       *) echo "Unknown" ;;
     esac
   }
   ```

3. **Update each skeleton's deps script** with new OS support

4. **Update documentation** in `_docs/DEPENDENCIES.md`

5. **Test the full workflow**:
   ```bash
   ./skel-deps --list
   ./skel-deps --help
   # Test on new OS
   ./skel-deps --all
   ```

#### Documentation Updates

When changing deps scripts, update:

1. **`_docs/DEPENDENCIES.md`**:
   - Installation commands for each OS
   - Version requirements
   - Troubleshooting tips

2. **`README.md`**:
   - Quick start examples
   - Supported systems list
   - Requirements section

3. **This file (`LLM-MAINTENANCE.md`)**:
   - Current dependencies list
   - OS-specific notes
   - Common patterns

---

## Critical Implementation Details

### `_bin/dev_skel_lib.py` (shared CLI library)

All `_bin/` Python CLIs depend on a single helper module. Key entry points:

- `load_config()` — merges defaults, environment, and `~/.dev_skel.conf`
  (sourced via a controlled subshell so shell-style expansion still works).
- `detect_root(script_dir, configured_skel_dir)` — locates the dev_skel
  checkout for relocatable invocations.
- `generate_project(root, skel_name, proj_name, service_override)` — performs
  the wrapper-aware generation, picks a unique service subdir
  (`backend-1`, `frontend-1`, `service-1`, …), and invokes the skeleton's
  `gen` script.
- `render_agents_template(target, service_subdir, skeleton_name, project_name)`
  — fills in `${project_name}`, `${service_dir}`, `${skeleton_name}`, and
  `${skeleton_doc}` in any `AGENTS.md` (and, where present, `CLAUDE.md`)
  shipped inside the generated project.
- `install_dev_dir`, `update_dev_dir`, `sync_to_remote` — rsync wrappers used
  by the install/update/sync CLIs.

Add new shared behaviour here rather than duplicating it across CLIs. Keep
the legacy `_bin/common.sh` untouched unless explicitly asked.

### `_skels/_common/AGENTS.md` template

`skel-gen` renders this template into every generated project so the result
ships with up-to-date agent rules. Placeholders use Python `string.Template`
syntax (`${name}`). When you add a new placeholder, also update the
`render_agents_template` context in `dev_skel_lib.py` so it actually gets
substituted.

### `_skels/_common/common-wrapper.sh` (multi-service wrapper scaffolder)

`common-wrapper.sh` is what turns a generated service into a wrapper-aware
project. It runs at the end of every skeleton's bash `gen` script and is
**idempotent** — re-running it as more services are added preserves the
existing `.env` and existing service directories.

Outputs in `<wrapper>/`:

- `.env` — created on the first run only (seeded from `.env.example`).
  Contains the wrapper-shared `DATABASE_URL` (default
  `sqlite:///_shared/db.sqlite3`), `JWT_SECRET`, `JWT_ALGORITHM`,
  `JWT_ISSUER`, `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL`, plus per-component
  `DATABASE_*` fallback variables.
- `.env.example` — always rewritten so the documented baseline stays in
  sync with the scaffolder. Commit this; do NOT commit `.env`.
- `_shared/README.md` and `_shared/db.sqlite3` — the shared layer (default
  SQLite database lives here).
- `README.md`, `Makefile` — wrapper-level docs and Make targets that
  delegate to the wrapper scripts (with optional `SERVICE=<slug>`).
- `services` — discovery script that lists every service whose directory
  contains an executable `install-deps`.
- Multi-service dispatch wrapper scripts for every executable script
  found in any service directory (`run`, `run-dev`, `test`, `build`,
  `build-dev`, `stop`, `stop-dev`, `install-deps`, `lint`, `format`,
  `deps`). Each script:
  1. Sources `<wrapper>/.env` so child processes inherit the shared env.
  2. Discovers services dynamically (any subdir that contains the matching
     script and is not `_shared` / hidden).
  3. If the first arg matches a service slug, dispatches only to that
     service. Otherwise:
     - **single-shot** scripts (`run`, `run-dev`, `lint`, `format`, `deps`)
       run on the first matching service.
     - **fan-out** scripts (`test`, `build`, `build-dev`, `stop`,
       `stop-dev`, `install-deps`) run on every matching service in order.

When you add a new wrapper script convention, edit the `SINGLE_SHOT_SCRIPTS`
or `FAN_OUT_SCRIPTS` arrays at the top of `common-wrapper.sh`.

### Backend skel env contract

Every backend skel — Python (`python-django-skel`,
`python-django-bolt-skel`, `python-fastapi-skel`, `python-flask-skel`),
Java (`java-spring-skel`), Rust (`rust-actix-skel`, `rust-axum-skel`), and
JS (`next-js-skel`) — follows the same env-driven config rule. Each settings
or config layer:

1. Loads `<wrapper>/.env` first (so the shared `DATABASE_URL` /
   `DATABASE_JDBC_URL` / `JWT_SECRET` etc. are visible) and the local
   service `.env` second so per-service overrides win.
2. Reads JWT material (`JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`,
   `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL`) from environment variables, never
   from a hardcoded constant or a Django-specific salt.
3. Resolves the database connection from a single shared variable, with
   a per-stack helper:
   - **Django / Django-Bolt** → `_build_databases()` reads `DATABASE_URL`
     (sqlite:/// or postgres://...) and falls back to
     `<wrapper>/_shared/db.sqlite3`.
   - **FastAPI / Flask** → `_resolve_database_url()` does the same,
     resolving sqlite paths relative to the wrapper.
   - **Spring Boot** → `application.properties` reads
     `${SPRING_DATASOURCE_URL:${DATABASE_JDBC_URL:jdbc:h2:mem:testdb}}`
     and the matching `SPRING_DATASOURCE_USERNAME` / `_PASSWORD`. The
     wrapper `.env` ships `SPRING_DATASOURCE_URL` and `DATABASE_JDBC_URL`
     side-by-side with `DATABASE_URL` so the JVM and Python services
     point at the same store.
   - **Rust (Actix / Axum)** → `src/config.rs::Config::from_env()`
     wraps `std::env::var` and exposes typed accessors. The bundled
     `load_dotenv()` walks up to the wrapper directory before reading
     local `.env`.
   - **JS (Node)** → `src/config.js` uses `dotenv` (already in
     `package.json`) to load `<service>/.env` first, then
     `<wrapper>/.env`, exposing a single `config` object with `databaseUrl`,
     `jwt`, and `service` namespaces.
4. JWT material is exposed as a single bean / module / object so handlers
   can `inject(JwtProperties)` (Spring), `import { config } from './config.js'`
   (Node), pull `web::Data<Arc<AppState>>` carrying the `Config` (Rust),
   or read `settings.JWT_SECRET` (Django).

When editing skel settings: never re-introduce a hardcoded sqlite path,
JWT secret, or a Django `SECRET_KEY` reference for token signing. The
env-driven flow is the contract that makes services in the same wrapper
interchangeable.

The wrapper `.env` ships `DATABASE_URL` (abstract / Python form),
`DATABASE_JDBC_URL` (JVM form), and `SPRING_DATASOURCE_URL` (Spring's
native variable name) side-by-side. When you switch the wrapper to
Postgres, update **all three** in lockstep — the dev_skel `.env.example`
documents this requirement.

### `_bin/skel_ai_lib.py` (legacy shim) + `_bin/skel_rag/` (RAG agent)

As of the 2026-04 RAG refactor, the AI orchestration lives in
`_bin/skel_rag/` and `_bin/skel_ai_lib.py` is a backwards-compat shim
that re-exports every public symbol used by `skel-gen-ai` and
`test-ai-generators`. The shim delegates the four orchestration
functions (`generate_targets`, `run_integration_phase`,
`run_test_and_fix_loop`, and the private `_ask_ollama_to_fix`) to
`skel_rag.agent.RagAgent`. `OllamaClient.chat` proxies to
`langchain_ollama.ChatOllama` via `skel_rag.llm`. Every other helper
(dataclasses, manifest loaders, dialogs, `format_prompt`,
`clean_response`, `build_system_prompt`, `expand_target_paths`,
`discover_siblings`, `run_service_tests`, the `_FIX_*` prompt
templates) is preserved verbatim because the agent imports it.

The RAG layer adds two new placeholders manifests can opt into:

* `{retrieved_context}` — Markdown rendering of the chunks retrieved
  from the **skeleton corpus** for the current per-target generation.
  Augments the legacy `{template}` placeholder (which keeps working).
* `{retrieved_siblings}` — Markdown rendering of the chunks retrieved
  from the **wrapper corpus** for the current integration target.
  Augments `{wrapper_snapshot}`.

Manifests that do not reference the new placeholders behave exactly
as before, so all 10 skeletons keep working without an opt-in.

#### `_bin/skel_rag/` package layout

| Module | Purpose |
| --- | --- |
| `config.py` | `OllamaConfig` (env-driven) and `RagConfig` (env-driven knobs: embedding model, top-K, max context chars, cache dir, fallback chunk size). |
| `chunker.py` | Code-aware chunker. Tree-sitter for Python / Java / TypeScript / Rust / Dart / JS / Go / C / C++ / C#; stdlib `ast` fallback for Python; `RecursiveCharacterTextSplitter` fallback for everything else. Each `CodeChunk` records `(file, language, kind, name, start_line, end_line, source)`. |
| `corpus.py` | `Corpus` discovery for a single skeleton or a generated wrapper. Reuses the `discover_siblings` skip set plus `.skel_rag_index`. `compute_manifest()` records `{rel_path: {mtime, size, sha[:16]}}` for cache invalidation. |
| `embedder.py` | Lazy `HuggingFaceEmbeddings` factory. Default model `BAAI/bge-small-en-v1.5` (~130 MB, normalisable). Cached at `~/.cache/dev_skel/embeddings/`. |
| `vectorstore.py` | `FAISS.load_local` / `FAISS.from_documents` wrapper with manifest-based cache invalidation. Persisted per skeleton at `_skels/<name>/.skel_rag_index/`; ephemeral (in-memory) for the wrapper integration phase. |
| `retriever.py` | `Retriever` with metadata-aware `similarity_search`. Filters by language, falls back to widening when fewer than `min_k` results match, and truncates the result to `max_context_chars` total. |
| `llm.py` | `ChatOllama` factory + `verify()` reachability check + `chat(config, system, user)` helper that mimics the legacy `OllamaClient.chat` signature. |
| `prompts.py` | `render_retrieved_block(chunks, max_chars)` — Markdown renderer for the `{retrieved_context}` / `{retrieved_siblings}` placeholders. `build_query_for_target(...)` — natural-language query builder used by the retriever. |
| `agent.py` | `RagAgent` — high-level orchestrator. `generate_targets`, `run_integration_phase`, `fix_target` methods. Maintains a per-corpus retriever cache keyed on `(corpus_id, root)`. |
| `cli.py` | argparse-based `skel-rag` CLI. Subcommands: `index`, `search`, `info`, `clean`. |

The shipped CLI is at `_bin/skel-rag` (a 20-line dispatcher that adds
`_bin/` to `sys.path` and calls `skel_rag.cli:main`). Examples:

```bash
# Build / refresh a skeleton's local FAISS index
_bin/skel-rag index _skels/python-fastapi-skel

# Inspect what the retriever returns for a query
_bin/skel-rag search "FastAPI repository CRUD" \
    --path _skels/python-fastapi-skel --language python

# Show stats about the persisted index
_bin/skel-rag info --path _skels/python-fastapi-skel

# Wipe the persisted index for one skeleton
_bin/skel-rag clean --path _skels/python-fastapi-skel
```

#### Installing dependencies

The RAG stack adds heavy dependencies (LangChain + sentence-transformers
+ FAISS + tree-sitter). They are loaded **lazily** inside
`_bin/skel_rag/` so the static-generation path (`_bin/skel-gen-static`)
keeps its stdlib-only contract; the legacy `{template}` /
`{wrapper_snapshot}` placeholders also keep working without the install
because the RAG agent falls back to a "_(retrieval disabled)_" string
when the imports fail.

```bash
make install-rag-deps
```

The Makefile target installs:

```
langchain-core langchain-community langchain-huggingface langchain-ollama
langchain-text-splitters sentence-transformers faiss-cpu tree-sitter
tree-sitter-languages
```

If `tree-sitter-languages` has no prebuilt wheel for your platform,
install `tree-sitter-language-pack` instead — the chunker auto-detects
both packages.

Convenience targets:

* `make rag-index-skels` — `skel-rag index` every skeleton in one go (CI
  warm-up so no developer pays the cold-build cost).
* `make rag-clean-skels` — wipe `.skel_rag_index/` from every skeleton.

#### Tunable knobs (env vars)

Every `RagConfig` field has a corresponding env var:

| Env var | Default | Notes |
| --- | --- | --- |
| `SKEL_RAG_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Override to swap in a heavier model (e.g. `BAAI/bge-base-en-v1.5` or `google/embeddinggemma-300m`). |
| `SKEL_RAG_INDEX_DIRNAME` | `.skel_rag_index` | Where the persisted FAISS index lives inside each corpus root. |
| `SKEL_RAG_CACHE_DIR` | `~/.cache/dev_skel/embeddings` | Embedding model download cache. |
| `SKEL_RAG_TOP_K` | `8` | Top-K for retrieval. |
| `SKEL_RAG_MIN_K` | `3` | Floor when language filtering rejects too many results. |
| `SKEL_RAG_MAX_CONTEXT_CHARS` | `12000` | Hard cap on the total characters injected into a single prompt's retrieved-context block. |
| `SKEL_RAG_CHUNK_MAX_CHARS` | `2000` | Per-chunk truncation. |
| `SKEL_RAG_FALLBACK_CHUNK_SIZE` / `SKEL_RAG_FALLBACK_CHUNK_OVERLAP` | `1500` / `150` | RecursiveCharacterTextSplitter parameters for unknown file types. |

The Ollama side uses `OLLAMA_HOST` as the primary knob (`host:port`);
`OLLAMA_BASE_URL` is an optional override that takes precedence when set.
Other env vars: `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_TEMPERATURE`.

#### Default account seeding

Every backend reads `USER_LOGIN`, `USER_EMAIL`, `USER_PASSWORD`,
`SUPERUSER_LOGIN`, `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD` from the
wrapper `.env` and creates the corresponding accounts at startup if
they don't already exist. The seed is idempotent. Login endpoints
across all backends accept either a username or an email address in
the `username` field (detected via `@`).

#### Legacy entry points (preserved by the shim)

- `OllamaConfig.from_env()` — reads `OLLAMA_HOST` (primary),
  `OLLAMA_BASE_URL` (optional override), `OLLAMA_MODEL`,
  `OLLAMA_TIMEOUT`, `OLLAMA_TEMPERATURE`. The `/v1` suffix on the
  resolved base URL is normalised away because the rest of the package
  appends the route segment itself.
- `OllamaClient.verify()` — proxies to `skel_rag.llm.verify`, which
  pings `/api/tags` and confirms the configured model is loaded
  locally; raises a friendly `OllamaError` otherwise.
- `OllamaClient.chat(system, user)` — proxies to `RagAgent.chat`, which
  invokes `langchain_ollama.ChatOllama` with the same temperature /
  timeout configured on the `OllamaConfig`.
- `GenerationContext` — dataclass holding the user's answers (service label,
  item name, auth type, auth notes) plus derived helpers (`item_class`,
  `items_plural`, `service_slug`, `auth_is_none`, `auth_required`). Its
  `as_template_vars()` method is the single source of truth for prompt
  placeholders.
- `prompt_user_dialog(...)` — interactive prompt that collects the missing
  pieces, honouring `--no-input` and CLI overrides.
- `load_manifest(repo_root, skeleton_name)` — loads
  `_skels/_common/manifests/<skel>.py` and validates the `MANIFEST` dict.
- `load_integration_manifest(repo_root, skeleton_name)` — loads the
  optional `INTEGRATION_MANIFEST` block from the same per-skel file.
  Returns `None` (not an exception) when no integration manifest is
  declared, so opt-in is the default for new skeletons.
- `discover_siblings(wrapper_root, exclude_slug)` — walks the wrapper
  directory and returns a `List[ServiceSummary]` for every sibling
  service. Each summary contains the slug, kind, detected tech, and a
  small map of `key_files: Dict[rel_path, contents]` (configured per
  skel via `_SIBLING_KEY_FILES`). The summaries get exposed to
  integration prompts via the `{wrapper_snapshot}` placeholder.
- `expand_target_paths(target, ctx)` — formats placeholders inside a
  target's `path`, `template`, and `description` so manifest entries can use
  `{service_slug}` etc. directly.
- `generate_targets(client, manifest, ctx, dry_run, progress)` — thin
  wrapper that delegates to `RagAgent.generate_targets`. The agent
  indexes the skeleton corpus once per call (cached on the client),
  retrieves the most relevant chunks per target, exposes them as
  `{retrieved_context}`, and still populates the legacy `{template}`
  placeholder so unmigrated manifests behave identically.
- `run_integration_phase(client, manifest, ctx, ...)` — thin wrapper
  that delegates to `RagAgent.run_integration_phase`. The agent builds
  an **ephemeral** wrapper-level corpus (in memory; not persisted to
  disk so wrapper directories stay clean) and exposes the results as
  both `{retrieved_context}` and `{retrieved_siblings}`, alongside the
  legacy `{wrapper_snapshot}` blob.
- `run_service_tests(test_command, ctx, *, timeout_s)` — runs the
  integration manifest's test command inside the new service
  directory, returning a `TestRunResult` with stdout/stderr/exit code
  whether the run passed or failed.
- `run_test_and_fix_loop(client, ctx, manifest, integration_results)` —
  bounded loop that runs the test command, asks the RAG agent to
  repair each failing integration file via `RagAgent.fix_target` (the
  agent enriches the prompt with retrieved sibling chunks scoped to
  the failing file), then re-runs. Bounded by `manifest.fix_timeout_m`
  minutes (default `60`; override with `FIX_TIMEOUT_M` env var).

### `_bin/skel-test-ai-generators` (AI end-to-end runner)

`_bin/skel-test-ai-generators` is the AI counterpart of `make test-generators`.
For every manifest under `_skels/_common/manifests/`, it:

1. Wipes any previous `_test_projects/test-ai-<skel>/` directory.
2. Runs the static `_bin/skel-gen` flow (so the wrapper, virtualenv, and
   skeleton template files all exist before the AI overlay touches them).
3. Loads the manifest, builds a `GenerationContext` from the default
   service / item / auth answers (overridable via flags), and calls
   `generate_targets` to write the AI-generated files.
4. Runs a per-skeleton validator:
   - `python-django-skel`: `manage.py check`.
   - `python-django-bolt-skel`: `manage.py check` + pytest collection on
     `app/tests`.
   - `python-fastapi-skel`: import the freshly generated
     `app/<service_slug>` module via the project's virtualenv.
   - All skeletons get a baseline `py_compile` syntax check.
5. Cleans up the directory on success unless `--keep` is set.

Selected flags:

- `--skel <name>` (repeatable) — limit the run to one or more skeletons.
- `--service-name`, `--item-name`, `--auth-type`, `--auth-details` —
  override the dialog defaults (`Sample Service` / `ticket` / `jwt`).
- `--ollama-model`, `--ollama-url`, `--ollama-temperature` — override
  Ollama config for this run only.
- `--dry-run` — skip the Ollama call entirely; only verifies that the
  base scaffold succeeds and the manifest paths resolve.
- `--skip-base` — reuse an existing `_test_projects/test-ai-<skel>/`
  instead of regenerating it.
- `--keep` — leave the result on disk after a successful run for manual
  inspection.

Exit codes: `0` (all passed), `1` (at least one skeleton failed),
`2` (Ollama unreachable / model missing — treated as a skip).

The runner is intentionally **not** part of `make test-generators`. AI
runs need a local Ollama daemon and can take 30+ minutes total against
the default `qwen3-coder:30b` model. Drop to a smaller coder model on
slower hardware:

```bash
OLLAMA_MODEL=qwen3-coder:30b OLLAMA_TIMEOUT=300 make test-ai-generators
```

Use the runner after editing a manifest, when bumping the default
model, or as part of a manual maintenance pass.

**Quality features** (all enabled by default):

* `--max-retries N` (default 1): on validation failure, cleans up
  generated files and re-runs the full generation.
* `--critique` / `--no-critique`: after generating each file, asks
  the same model to review it against the system prompt's
  CRITICAL/Coding rules. On FAIL, re-generates with the critique
  reason appended. Capped at 1 critique per file.
* **Multi-phase context**: each target in `generate_targets`
  accumulates its output and passes it to subsequent targets via the
  `{prior_outputs}` placeholder (implemented in
  `_bin/skel_rag/agent.py`). Later targets (tests) see the exact
  code earlier targets (models) produced.

**INTEGRATION_MANIFEST**: all 10 AI-supported skeletons ship an
`INTEGRATION_MANIFEST` with sibling-client targets + integration test
targets. These run as a second Ollama pass after the per-target
manifest and produce cross-service wiring code. Each manifest
declares a `test_command` for the bounded test-and-fix loop.

To add a new AI-supported skeleton, drop a manifest under
`_skels/_common/manifests/` (the runner will auto-discover it) and, if
the validation step needs more than the baseline syntax check, add an
entry to `VALIDATORS` in `_bin/skel-test-ai-generators`.

### Project-wide `./ai` memory + wrapper-level dispatch

Two layers turn the per-service `./ai` into a project-wide tool:

**1. Wrapper-level `<wrapper>/ai` dispatcher** — auto-generated by
`common-wrapper.sh`'s "single" dispatch template. Three modes:

```
./ai "REQUEST"                     # forwards to the FIRST service
./ai <service-slug> "REQUEST"      # forwards to a specific service
./ai --all "REQUEST"               # FAN-OUT — runs the request against
                                    # EVERY service in the wrapper
```

The `--all` flag is the cross-service refactor mode: a single
request ("rename Item to Task throughout the project") lands in
every backend + frontend that has `./ai`. Failures accumulate; the
final exit code is the last non-zero status. The `--all`
recogniser is implemented in `common-wrapper.sh:write_dispatch_script`
and applies to **every** "single"-mode wrapper script — so
`./backport --all` works the same way for batch backporting.

**2. Cross-call AI memory** — every `./ai apply` writes a single
JSONL entry to two files:

* `<service>/.ai/memory.jsonl` — per-service log
* `<wrapper>/.ai/memory.jsonl` — project-wide log (shared across
  every service in the wrapper)

The next `./ai propose` (in any service of the wrapper) loads the
last 5 entries from the wrapper-shared file and prepends them to
the LLM prompt as a `## PREVIOUS_AI_RUNS` block. The model sees
what was done before, whether it passed tests, and which files
were edited — gaining continuity across invocations and across
services.

Entry shape:

```json
{
  "ts":           "2026-04-16T18:03:21Z",
  "service":      "items_api",
  "request":      "extract a service layer ...",
  "edited_files": ["app/items/service.py", "app/items/depts.py"],
  "rationale":    "<truncated to 800 chars>",
  "passed":       true,
  "returncode":   0
}
```

Memory is **never an apply blocker**: write failures swallow
silently, malformed JSONL lines are skipped on read.

`./ai history` renders both layers (project memory across
services + local scratch runs in this service).

**Files**:

* `_bin/dev_skel_refactor_runtime.py` — `_memory_paths`,
  `_append_memory`, `_load_recent_memory`, `_format_memory_block`,
  `_record_apply_to_memory`, `_load_project_memory_block`. Wired
  into both `MinimalRunner.propose` (raw prompt) and
  `RagRunner.propose` (prepended to retrieved context). The
  post-apply branches in `main()` call `_record_apply_to_memory`
  on PASS, on rollback FAIL, and on `--no-verify`.
* `_skels/_common/common-wrapper.sh:write_dispatch_script` — the
  shared dispatch template that emits the `--all` recogniser into
  every wrapper-level script.
* `_bin/skel-test-ai-memory` — smoke harness (no Ollama). Backs
  `make test-ai-memory`.

**Operator commands**:

* `make test-ai-memory` — verifies wrapper dispatch +
  memory-write round-trip + history aggregation (no LLM).

### `./backport` (service-local skeleton backport)

A per-service shim that forwards to the maintainer-side
`_bin/dev_skel_backport.py`. Lets the developer run a
**service → template** propagation directly from inside their
generated service, without having to switch back to the dev_skel
root or remember the maintainer CLI's argument order.

**Subcommands**:

```
./backport               # alias of `propose` (dry-run)
./backport propose       # list every service file that differs
                         # from its same-relative skeleton file
./backport apply         # write the changes back into the skel
./backport --help        # full surface area
```

**Sidecar**: reads `.skel_context.json` in the service dir to
know which skeleton to write to. The sidecar is created by
`install-ai-script` when `common-wrapper.sh` runs:

* Each per-skel `gen` exports `SKEL_NAME="$(basename "$SKEL_DIR")"`
  before invoking `common-wrapper.sh`.
* `common-wrapper.sh` calls `install-ai-script <svc> "$SKEL_NAME"
  force` for the just-generated `PROJECT_SUBDIR`. Sibling services
  get a non-force install so their existing sidecars are preserved.

**Activation**: REQUIRES a reachable dev_skel checkout (the script
writes back into `_skels/`). Auto-detection mirrors `./ai`:
`$DEV_SKEL_ROOT` → walk-up looking for `_skels/` + `_bin/skel-gen-ai`
+ `_bin/dev_skel_backport.py` → `~/dev_skel`, `~/src/dev_skel`,
`/opt/dev_skel`, `/usr/local/share/dev_skel`. Detached services
exit 1 with an actionable error.

**Output**: every run drops a JSON summary to
`<dev_skel>/.ai/backport/<ts>-<sha>/result.json` listing every
candidate (`rel_path`, `service_path`, `skeleton_path`, `reason`).
On `apply`, the same payload includes the files that were written.

**Files**:

* `_skels/_common/refactor_runtime/backport` — per-service shim
  (~120 lines, pure Python, no third-party imports).
* `_skels/_common/refactor_runtime/install-ai-script` — also
  installs `./backport` next to `./ai` and writes the
  `.skel_context.json` sidecar.
* `_bin/dev_skel_backport.py` — maintainer-side propose/apply
  engine. Pure file-diff (no LLM involvement); only candidates
  whose relative paths already exist inside the target skeleton are
  considered backportable.
* `_bin/skel-backport` — top-level CLI wrapper around
  `dev_skel_backport.main`.
* `_bin/skel-test-backport-script` — propose+apply round-trip
  smoke (generates fastapi service → mutates `app/__init__.py` →
  asserts skel updated → `git checkout`-restores). Backs the
  `make test-backport-script` target.

**Operator commands**:

* `make test-backport-script` — cheap propose+apply smoke (no LLM).
  Now also asserts that `apply` bumps `<skel>/VERSION` (semver
  patch) and prepends a `## [VERSION] - DATE` entry to
  `<skel>/CHANGELOG.md`.
* `make test-ai-script` — sibling smoke for `./ai`.
* `make test-ai-upgrade` — no-LLM smoke for `./ai upgrade`
  (no-op + outdated paths).
* `make test-ai-fanout` — no-LLM smoke for the wrapper-level
  `./ai` fan-out default (two-service wrapper).
* `_bin/skel-backport propose <service>` /
  `_bin/skel-backport apply <service>` — the underlying maintainer
  CLI (forwarded to by `./backport`).

**Versioning side effect** (since 2026-04): every accepted
backport bumps the skel's `VERSION` and writes a changelog entry.
This is what `./ai upgrade` (next section) uses to know which
changes to replay against an already-generated service. Best-effort
— write failures emit a warning and do not abort the apply.

### `./ai` (service-local AI refactoring)

A per-service script + vendored runtime that lets developers run
AI-driven refactors **inside** a generated service. Three discrete
"AI-leverage surfaces" of dev_skel:

| Tool | Direction | Where it runs | What it touches |
| ---- | --------- | ------------- | --------------- |
| `_bin/skel-gen-ai` | template → service | dev_skel root | writes the generated service |
| `_bin/skel-backport` | service → template | dev_skel root | writes the skel templates |
| **`./ai`** | service → service | inside the generated service | rewrites the service's own code |

**Subcommands** (run from inside a generated service dir):

```
./ai "REQUEST"           # default: propose, dry-run
./ai apply "REQUEST"     # propose + apply + verify (fix loop)
./ai verify              # re-run last proposal's fix loop
./ai explain             # last run's per-file rationale
./ai history             # list past runs
./ai undo                # revert last applied refactor
./ai upgrade             # pull skel changes since this service was generated
                         # (dry-run; pass --apply to commit)
```

**Wrapper-level dispatch defaults to fan-out** (since 2026-04). At
the project root, `./ai "REQUEST"` runs the request against every
service in the wrapper; `./ai <slug> "REQUEST"` still scopes to one
service. Same applies to `./ai upgrade` and `./backport`. The
`--all` flag is now redundant and kept only for backwards
compatibility.

**Two activation modes** (auto-detected by `detect_devskel`):

* **In-tree** — dev_skel checkout reachable. Imports
  `skel_rag.agent.RagAgent` (FAISS + sentence-transformers) and
  `skel_ai_lib.run_test_and_fix_loop`. Same call stack as
  `skel-gen-ai`.
* **Out-of-tree** — service detached from dev_skel. Stdlib-only
  retrieval (ripgrep with a pathlib fallback) + a bundled minimal
  fix-loop in `.ai_runtime.py`. No third-party imports beyond the
  stdlib + a single `urllib.request` to Ollama.

**Env vars** (in addition to `OLLAMA_*`):

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DEV_SKEL_ROOT` | unset | Force in-tree mode pointing at a specific dev_skel checkout. |
| `SKEL_REFACTOR_FIX_TIMEOUT_M` | `15` | Fix-loop budget (minutes). |
| `SKEL_REFACTOR_MAX_FILES` | `8` | Hard cap on files the LLM may edit per run. |

**Output layout** (per run, in `<service>/.ai/<ts>-<sha>/`):

```
.ai/
├── <ts>-<sha>/
│   ├── request.txt              # the user's natural-language request
│   ├── context.json             # resolved RefactorContext
│   ├── retrieved/chunks.md      # rendered RAG retrieval block
│   ├── proposals/<rel>.proposed # one file per proposed edit
│   ├── rationale.md             # per-file rationale
│   ├── applied.json             # populated only after --apply
│   └── verification.log         # populated only after fix-loop runs
└── HEAD                         # symlink to the latest run dir
```

The `.ai/` directory is git-ignored — `install-ai-script` appends
`.ai/` to the service `.gitignore` on first install.

**Safety contract** (cannot be defeated by adversarial LLM output):

* Every write is checked against `service_dir.resolve()` and skipped
  if it lands outside.
* `apply` refuses to run on a dirty git tree without `--allow-dirty`.
* Pre-apply state captured to a git stash; verification failure ⇒
  `git stash pop` to restore.
* Per-service `.ai/.lock` (O_CREAT|O_EXCL) prevents concurrent
  applies.
* Path traversal (`../`, absolute paths, `.git`, `.ai`,
  `node_modules`, `.venv`) is rejected by both the parser and the
  applier.

**Files**:

* `_bin/dev_skel_refactor_runtime.py` — canonical source of truth
  (RefactorContext, FileEdit, AppliedResult, RagRunner,
  MinimalRunner, `_apply_edits_with_stash`, `_minimal_fix_loop`,
  CLI dispatch, `_self_test()`). Run
  `python3 _bin/dev_skel_refactor_runtime.py --self-test` to verify
  parser sanity.
* `_bin/skel-ai` — top-level CLI for driving `./ai` from outside a
  service: `_bin/skel-ai SERVICE_DIR "REQUEST" [flags]`.
* `_skels/_common/refactor_runtime/ai` — the per-service script
  (identical for every skel; bootstraps the runtime).
* `_skels/_common/refactor_runtime/dev_skel_refactor_runtime.py` —
  vendored copy, kept in sync via `make sync-ai-runtime`.
* `_skels/_common/refactor_runtime/install-ai-script` — installer
  invoked by `common-wrapper.sh` for every service in the wrapper.
* `_skels/_common/common-wrapper.sh` — calls
  `install-ai-script <service>` per service before laying down the
  fan-out dispatch scripts.
* `_bin/skel_rag/agent.py:RagAgent.refactor_files` — the in-tree
  LLM call.
* `_bin/skel_rag/prompts.py` — `REFACTOR_SYSTEM_PROMPT`,
  `REFACTOR_USER_PROMPT`, `build_query_for_refactor`.
* `_bin/skel-test-ai-script` — cheap dispatch smoke (no Ollama;
  generates a fastapi service, runs `./ai --no-llm`, asserts
  scratch dir + history are populated).

**Operator commands**:

* `make sync-ai-runtime` — copy the canonical runtime into the
  vendored slot. Run after editing
  `_bin/dev_skel_refactor_runtime.py` so newly-generated services
  pick up the changes.
* `make test-ai-script` — dispatch smoke (no Ollama).
* `make test-ai-upgrade` — `./ai upgrade` no-op + outdated paths
  (no Ollama).
* `make test-ai-fanout` — wrapper-level `./ai` fan-out default
  across two services (no Ollama).

**Skeleton versioning + `./ai upgrade`** (since 2026-04):

* Each `_skels/<name>/` ships a `VERSION` file (semver) + a
  `CHANGELOG.md` (Keep-a-Changelog format).
* `install-ai-script` reads `<skel>/VERSION` and writes
  `skeleton_version` into the service sidecar.
* `_bin/skel-backport apply` bumps `<skel>/VERSION` (semver patch)
  and prepends a `## [VERSION] - DATE` entry to
  `<skel>/CHANGELOG.md` listing each backported file.
* `./ai upgrade` reads `skeleton_version` from the sidecar,
  compares to `<skel>/VERSION`, extracts the matching CHANGELOG
  entries, and synthesises an AI request that asks the model to
  apply those changes to the service. Dispatched through the
  standard propose/apply flow so all safety machinery still
  applies. Sidecar `skeleton_version` is rewritten on successful
  apply.
* Implementation: `_cmd_upgrade` + `_changelog_excerpt` /
  `_semver_tuple` in `_bin/dev_skel_refactor_runtime.py`,
  `_bump_skeleton_version` + `_bump_patch` in
  `_bin/dev_skel_backport.py`, `FAN_OUT_SCRIPTS` in
  `_skels/_common/common-wrapper.sh`.

**Design doc**: `SERVICE_REFACTOR_COMMAND.md` (full spec —
subcommands, fixtures, fix-loop strategy, security tests).

### `_skels/_common/manifests/` (AI generation manifests)

Each AI-supported skeleton ships a manifest file at
`_skels/_common/manifests/<skeleton-name>.py` exposing a top-level
`MANIFEST` dict with this shape:

```python
SYSTEM_PROMPT = """..."""

MANIFEST = {
    "system_prompt": SYSTEM_PROMPT,
    "notes": "post-generation hint shown to the user",
    "targets": [
        {
            "path": "{service_slug}/models.py",
            "template": "myproject/models.py",  # optional, relative to skel root
            "language": "python",
            "description": "models.py — main entity",
            "prompt": """...{item_class}... REFERENCE: ---\n{template}\n---""",
        },
    ],
}
```

Available placeholders inside `path`, `template`, `description`, and
`prompt`: `skeleton_name`, `project_name`, `service_subdir`, `service_label`,
`service_slug`, `item_name`, `item_class`, `items_plural`, `auth_type`,
`auth_details`, `auth_is_none`, `auth_required`, plus uppercase variants
(`SERVICE_SLUG`, `ITEM_NAME`, `ITEM_CLASS`, `ITEMS_PLURAL`) for embedding
constant names directly (`{ITEMS_PLURAL}_BASE` → `TASKS_BASE`), plus the
special `{template}` slot inside prompts (the contents of the referenced
template file). Manifests live outside the skeleton tree so the per-skeleton
`merge` scripts do not need to learn about them.

#### Optional `INTEGRATION_MANIFEST` block

The same per-skel manifest file may declare a second top-level dict
named `INTEGRATION_MANIFEST` with the same shape as `MANIFEST` plus
two extra fields:

```python
INTEGRATION_MANIFEST = {
    "system_prompt": "...",       # rendered with {wrapper_snapshot} etc.
    "targets": [...],             # additive — never overwrite first-pass files
    "test_command": "./test app/tests/test_integration.py -q",  # default: "./test"
    "fix_timeout_m": 120,         # default: 120 (minutes)
    "notes": "...",
}
```

When present, `_bin/skel-gen-ai` runs a **second Ollama session**
after the per-target generation finishes. The integration prompts get
two extra placeholders: `{wrapper_snapshot}` (Markdown rendering of
every sibling service's slug, kind, tech, and key files) and
`{sibling_count}` / `{sibling_slugs}`. The phase is silently skipped
when `INTEGRATION_MANIFEST` is absent. After the integration files
are written, `skel-gen-ai` runs a bounded test-and-fix loop:

1. Execute `test_command` inside the new service directory.
2. If exit ≠ 0, ask Ollama to repair each integration file (one
   round-trip per file) using a "fix" system prompt that includes
   the current file contents + truncated test output.
3. Re-run until pass or `fix_timeout_m` minutes elapse (default 120).

CLI knobs: `--no-integrate` skips the integration phase entirely;
`--no-test-fix` runs the integration phase but skips the loop. Both
default-on so a fresh `skel-gen-ai` run produces a fully integrated
service out of the box.

The canonical example of an `INTEGRATION_MANIFEST` lives in
`_skels/_common/manifests/python-django-bolt-skel.py` (3 targets:
`app/integrations/__init__.py`, `app/integrations/sibling_clients.py`,
`app/tests/test_integration.py`). Copy and adapt for the other
skels as you write them.

`service_subdir` is the **slug of the user's chosen service display name**
(`Ticket Service` → `ticket_service`). It is decided BEFORE Ollama is
called, so manifest paths and prompts can reference it freely.

When writing settings/config prompts, ALWAYS keep the wrapper-shared
`.env` loading block and JWT/DATABASE env reads intact. The contract is:
backend services read `JWT_SECRET` / `DATABASE_URL` from
`<wrapper>/.env` so a token issued by one service is accepted by every
other service in the same wrapper. Manifests must never tell Ollama to
hardcode a sqlite path or use `settings.SECRET_KEY` for token signing —
the correct attribute is `settings.JWT_SECRET`.

To add support for a new skeleton: drop a `<skeleton-name>.py` file under
`_skels/_common/manifests/` and run a dry-run smoke test:

```bash
_bin/skel-gen-ai myproj <skeleton-name> --no-input --dry-run --skip-base
```

(Create an empty target directory first, since `--skip-base` expects the
project to exist already.)

### merge script contract

- The `merge` script signature is: `merge <SKEL_DIR> <TARGET_DIR>`.
- It must:
  - Echo progress and copied relative paths (optional but helpful).
  - Exclude generator-owned files for that stack (see `_skels/*/merge`).
  - Only copy if destination file does not exist (never overwrite).
  - Create parent directories as needed.

### Framework-Specific Considerations

**ts-react-skel**:
- Uses `npm create vite@latest` which creates its own config files
- Excludes `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts` from merge

**python-django-skel**:
- Uses `django-admin startproject` then overlays skeleton
- Excludes `manage.py` and key `myproject/*` files from merge

**rust-*-skel**:
- Uses `cargo new` then overlays skeleton
- Excludes `Cargo.toml` and `src/main.rs` from merge

---

## Testing Protocol

### After Any Change

1. **Clean test environment**:
   ```bash
   make clean-test
   ```

2. **Run all generator tests**:
   ```bash
   make test-generators
   ```

3. **Verify output**:
   - All 10 generators should pass
   - Check for any warnings or unexpected output

### Test Output Expectations

```
=== Testing all generators ===
>>> Testing FastAPI generator
...
FastAPI generator test passed
>>> Testing Flask generator
...
Flask generator test passed
... (6 more) ...
=== All generators tested successfully! ===
```

---

## File Locations Quick Reference

| Purpose | Location |
|---------|----------|
| Main Makefile | `./Makefile` |
| Main dependency installer | `./skel-deps` |
| Helper tools (Python CLIs) | `_bin/` |
| Shared CLI library | `_bin/dev_skel_lib.py` |
| AI generator library (Ollama) | `_bin/skel_ai_lib.py` |
| AI generator CLI | `_bin/skel-gen-ai` |
| AI end-to-end test runner | `_bin/skel-test-ai-generators` |
| Per-skeleton AI manifests | `_skels/_common/manifests/<skel>.py` |
| Common skeleton assets | `_skels/_common/` |
| Common AGENTS template | `_skels/_common/AGENTS.md` |
| Wrapper scaffolder | `_skels/_common/common-wrapper.sh` |
| Skeletons | `_skels/*/` |
| Skeleton Makefiles | `_skels/*/Makefile` |
| Skeleton generators | `_skels/*/gen` |
| Skeleton merge scripts | `_skels/*/merge` |
| Skeleton test scripts | `_skels/*/test` |
| System dependency installers | `_skels/*/deps` |
| Project dependency installers | `_skels/*/install-deps` (copied to projects) |
| Documentation | `_docs/` |
| Test output | `_test_projects/` |
| Cross-agent rules | `/AGENTS.md` |
| Claude-specific rules | `/CLAUDE.md` |

---

## Do NOT

- **Do NOT** modify files in `_test_projects/` - it's auto-generated
- When you need to create a new test app manually during maintenance, create
  it under `_test_projects/` only (e.g. `make gen-fastapi NAME=_test_projects/my-fastapi-repro`).
- **Do NOT** commit `node_modules/`, `.venv/`, `target/` directories
- **Do NOT** change the `SKEL_DIR` detection pattern - it's carefully designed
- Prefer absolute/abspath usage to avoid relative path issues
- **Do NOT** add interactive prompts to generators (must work non-interactively)

---

## Maintenance Checklist

When maintaining this project, ensure:

- [ ] All 10 generators pass: `make test-generators`
- [ ] All 10 dependency scripts are executable: `ls -l _skels/*/deps`
- [ ] No hardcoded absolute paths in Makefiles or scripts
- [ ] `merge` scripts' exclusions are up to date
- [ ] `deps` scripts support all target platforms (macOS, Ubuntu, Arch, Fedora)
- [ ] Documentation reflects current state
- [ ] Skeleton source code is functional and follows best practices
- [ ] Dependencies are reasonably current (check for security issues)
- [ ] `skel-deps --list` shows all skeletons with ✓ status

---

## Contact

This project is maintained by the repository owner. For issues:
1. Check existing documentation
2. Run `make test-generators` to identify problems
3. Review recent changes to Makefiles
