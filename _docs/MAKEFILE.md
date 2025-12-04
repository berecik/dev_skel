# Makefile Reference

## Overview

The main `Makefile` orchestrates project generation by delegating to individual skeleton Makefiles. Each skeleton contains its own `Makefile` with a `gen` target that delegates to the skeleton's Bash `gen` script (which contains the full generation logic) and a `test` target that runs an end-to-end validation via `bash ./test`.

## Architecture

```
Main Makefile
    │
    ├── gen-fastapi ──► _skels/python-fastapi-skel/Makefile (gen target)
    ├── gen-flask ────► _skels/python-flask-skel/Makefile (gen target)
    ├── gen-django ───► _skels/python-django-skel/Makefile (gen target)
    ├── gen-vite-react► _skels/ts-vite-react-skel/Makefile (gen target)
    ├── gen-js ───────► _skels/js-skel/Makefile (gen target)
    ├── gen-spring ───► _skels/java-spring-skel/Makefile (gen target)
    ├── gen-actix ────► _skels/rust-actix-skel/Makefile (gen target)
    └── gen-axum ─────► _skels/rust-axum-skel/Makefile (gen target)
```

## Variables

### Directory Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SKEL_DIR` | `_skels` | Base directory containing all skeletons |
| `TEST_OUTPUT` | `_test_projects` | Directory for test-generated projects |
| `FASTAPI_SKEL` | `$(SKEL_DIR)/python-fastapi-skel` | FastAPI skeleton path |
| `FLASK_SKEL` | `$(SKEL_DIR)/python-flask-skel` | Flask skeleton path |
| `DJANGO_SKEL` | `$(SKEL_DIR)/python-django-skel` | Django skeleton path |
| `VITE_REACT_SKEL` | `$(SKEL_DIR)/ts-vite-react-skel` | Vite+React skeleton path |
| `JS_SKEL` | `$(SKEL_DIR)/js-skel` | JavaScript skeleton path |
| `SPRING_SKEL` | `$(SKEL_DIR)/java-spring-skel` | Spring Boot skeleton path |
| `ACTIX_SKEL` | `$(SKEL_DIR)/rust-actix-skel` | Actix-web skeleton path |
| `AXUM_SKEL` | `$(SKEL_DIR)/rust-axum-skel` | Axum skeleton path |
| `SKELETONS` | All above | List of all skeleton directories |

### Color Codes

| Variable | Value | Usage |
|----------|-------|-------|
| `GREEN` | `\033[0;32m` | Success messages |
| `YELLOW` | `\033[0;33m` | Warnings, progress |
| `BLUE` | `\033[0;34m` | Help text |
| `RED` | `\033[0;31m` | Errors |
| `NC` | `\033[0m` | Reset color |

## Targets

### Generator Targets

| Target | Usage | Description |
|--------|-------|-------------|
| `gen-fastapi` | `make gen-fastapi NAME=myapp` | Generate Python FastAPI project |
| `gen-flask` | `make gen-flask NAME=myapp` | Generate Python Flask project |
| `gen-django` | `make gen-django NAME=myapp` | Generate Python Django project |
| `gen-vite-react` | `make gen-vite-react NAME=myapp` | Generate TypeScript Vite+React project |
| `gen-js` | `make gen-js NAME=myapp` | Generate JavaScript/Node.js project |
| `gen-spring` | `make gen-spring NAME=myapp` | Generate Java Spring Boot project |
| `gen-actix` | `make gen-actix NAME=myapp` | Generate Rust Actix-web project |
| `gen-axum` | `make gen-axum NAME=myapp` | Generate Rust Axum project |

All generator targets:
- Require `NAME` parameter
- Convert `NAME` to absolute path before delegating
- Delegate to skeleton's `gen` target via `$(MAKE) -C $(SKEL) gen NAME=$(abspath $(NAME))`

### Test Targets

| Target | Description |
|--------|-------------|
| `test-generators` | Run all generator tests (creates projects in `_test_projects/`) |
| `test-gen-fastapi` | Test FastAPI generator |
| `test-gen-flask` | Test Flask generator |
| `test-gen-django` | Test Django generator |
| `test-gen-vite-react` | Test Vite+React generator |
| `test-gen-js` | Test JavaScript generator |
| `test-gen-spring` | Test Spring Boot generator |
| `test-gen-actix` | Test Actix generator |
| `test-gen-axum` | Test Axum generator |
| `test-all` | Run tests within each skeleton directory (calls `bash ./test`) |
| `test-fastapi` | Run FastAPI skeleton tests |
| `test-flask` | Run Flask skeleton tests |
| `test-django` | Run Django skeleton tests |
| `test-vite-react` | Run Vite+React skeleton tests |
| `test-js` | Run JavaScript skeleton tests |
| `test-spring` | Run Spring Boot skeleton tests |
| `test-actix` | Run Actix skeleton tests |
| `test-axum` | Run Axum skeleton tests |

### Utility Targets

| Target | Description |
|--------|-------------|
| `help` | Show available targets with descriptions |
| `list` | List all skeleton projects |
| `status` | Show status of skeleton directories (exists/missing) |
| `info-all` | Show info for all skeleton projects |
| `clean-all` | Clean all skeleton projects |
| `clean-test` | Remove `_test_projects/` directory |

## Skeleton Makefile Structure

Each skeleton's `Makefile` follows this pattern:

```makefile
# Skeleton Name - Makefile

.PHONY: gen test

# Auto-detect skeleton directory (works regardless of where make is called from)
SKEL_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# Standard scripts
GEN := $(SKEL_DIR)/gen
MERGE := $(SKEL_DIR)/merge

gen: ## Generate project (NAME=myapp)
ifndef NAME
    @echo "Usage: make gen NAME=<project-name>"
    @exit 1
endif
    @bash $(GEN) "$(NAME)"

test: ## Generate a temp project and run its tests (e2e)
    @bash ./test
```

### Key Points

1. **SKEL_DIR Detection**: Uses `$(dir $(abspath $(lastword $(MAKEFILE_LIST))))` to auto-detect the skeleton directory path, ensuring correct operation whether called directly or via the main Makefile.

2. **gen Script**:
   - Each skeleton ships an executable `gen` Bash script that contains ALL generation logic (scaffolding, dependency installation, and calling `merge`).
   - Skeleton Makefiles must delegate to it with: `bash $(SKEL_DIR)/gen "$(NAME)"`.

3. **merge Script**:
   - Each skeleton ships an executable `merge` script that copies auxiliary files into the newly generated project without overwriting generator-owned files (e.g., `Cargo.toml`, `package.json`, framework-initialized sources).
   - The `gen` script invokes it with: `bash "$SKEL_DIR/merge" "$SKEL_DIR" "$TARGET"`.

3. **NAME Parameter**: All `gen` targets require `NAME` to be set and should be an absolute path when called from the main Makefile.

4. **Test Scripts**: Each skeleton contains a `test` Bash script that generates into a temporary directory, runs the project's tests, and performs a non-interactive run/build check. The skeleton `Makefile` simply delegates to `bash ./test`.

## Adding a New Skeleton

1. Create new directory: `_skels/language-framework-skel/`
2. Add skeleton files with working example code
3. Create `Makefile` with `gen` and `test` targets
   - Use `GEN := $(SKEL_DIR)/gen` and delegate `gen` to `@bash $(GEN) "$(NAME)"`.
   - Keep `test` delegating to `bash ./test`.
4. Add an executable `merge` script that implements copy logic and excludes generator-owned files.
5. Add an executable `gen` script that wraps `make -C "$SKEL_DIR" gen NAME="$TARGET"`.
6. Add an executable `test` script that generates into a temp dir and validates non-interactively.
7. Add variables to main Makefile:
   ```makefile
   NEW_SKEL := $(SKEL_DIR)/language-framework-skel
   SKELETONS := ... $(NEW_SKEL)
   ```
8. Add generator target:
   ```makefile
   gen-new: ## Generate New Framework project (NAME=myapp)
       @$(MAKE) -C $(NEW_SKEL) gen NAME=$(abspath $(NAME))
   ```
9. Add test targets (`test-gen-new`, `test-new`)
10. Update `.PHONY` declarations
11. Run `make test-generators` to verify

## Generator Tool

You can also generate projects from anywhere using the relocatable tool:

```bash
_bin/skel-gen <skel-name> <target-path>
```

The tool prefers a skeleton's `gen` script (which contains all logic) and falls back to `make -C <skel> gen NAME=<target>` if missing.
