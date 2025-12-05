# Skeleton Templates Reference

## Overview

Each skeleton is a complete, working project template that can be used to bootstrap new projects. Skeletons include:
- Source code with example implementations
- Configuration files
- Test setup
- Development tooling

### Common conventions

- **Generation**
  - From repo root: `make gen-<name> NAME=<target-path>` (delegates to the skeleton's `gen` script)
  - From anywhere: `_bin/skel-gen <skel-name> <target-path>` (prefers per-skeleton `gen` script)
  - From skeleton dir: `bash ./gen <target-path>` (the `gen` script contains ALL generation logic)
- **Generated layout (wrapper + inner project)**
  - The `NAME` / `target-path` you pass is the **wrapper directory** (`main_dir`).
  - The real framework-specific project lives in a per-skeleton subdirectory (`project_dir`) inside `main_dir`:
    - Python backends (FastAPI, Flask, Django): `backend/`
    - React frontend (ts-react-skel): `frontend/`
    - Node.js (js-skel): `app/`
    - Java Spring, Rust Actix, Rust Axum: `service/`
  - A common wrapper script (`_skels/_common/common-wrapper.sh`) creates in `main_dir`:
    - A generic `README.md` and `Makefile`.
    - Thin wrapper scripts (`./run`, `./test`, `./build`, `./stop`, `./install-deps`, etc.) that **forward all arguments** to matching scripts in `project_dir/`.
- **Testing**
  - From skeleton dir: `make test` which runs `bash ./test`
  - E2E skeleton tests: `./test_skel` generates into a temporary directory, uses the wrapper layout, runs tests, and builds Docker image
- **Build/Run/Stop**
  - `./build` - Build Docker image (with options like `--no-cache`, `--tag=`, framework-specific like `--jar`, `--release`, `--local`)
  - `./run` - Run development server (modes: `dev`, `prod`, `docker`)
  - `./stop` - Stop running Docker containers
- **Merge script**
  - Each skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`
  - It copies auxiliary files into the generated project without overwriting generator-owned files

### Scripts available in generated projects

| Script | Description | Common Options |
|--------|-------------|----------------|
| `./test` | Run project tests | `-q` (quiet), `--cov` (coverage) |
| `./build` | Build Docker image | `--tag=NAME`, `--no-cache`, `--push` |
| `./run` | Run server | `dev`, `prod`, `docker` |
| `./stop` | Stop services | - |

Framework-specific build options:
- **Java Spring**: `./build --jar` - Build JAR only
- **Rust**: `./build --release` - Build release binary
- **Vite/React**: `./build --local` - Build locally (npm run build)

## Available Skeletons

### Python

- [python-fastapi-skel](./python-fastapi-skel.md) - FastAPI with async SQLAlchemy
- [python-flask-skel](./python-flask-skel.md) - Flask with Flask-SQLAlchemy
- [python-django-skel](./python-django-skel.md) - Django

### TypeScript/JavaScript

- [ts-react-skel](./ts-react-skel.md) - React + Vite + TypeScript + Vitest
- [js-skel](./js-skel.md) - Plain JavaScript/Node.js

### Java

- [java-spring-skel](./java-spring-skel.md) - Spring Boot

### Rust

- [rust-actix-skel](./rust-actix-skel.md) - Actix-web
- [rust-axum-skel](./rust-axum-skel.md) - Axum

## Merge Script Typical Exclusions

Each skeleton ships a `merge` Bash script to copy auxiliary files into the generated project without overwriting generator-owned files. Typical exclusions include:

**Shared directories and caches:**
- `.venv/`, `node_modules/`, `target/`, `__pycache__/`, `.git/`, `dist/`, `build/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`

**Shared files and helpers:**
- `Makefile`, `merge`, `gen`, `test`, `*.pyc`, `*.pyo`, `*.class`, `*.db`, `*.sqlite`, `*.sqlite3`

**Stack-specific exclusions:**
- Python Django: `manage.py`, `myproject/__init__.py`, `myproject/asgi.py`, `myproject/settings.py`, `myproject/urls.py`, `myproject/wsgi.py`
- JavaScript (Node): `package.json`, `package-lock.json`
- TS React: `package.json`, `package-lock.json`, `tsconfig.json` (vite.config.ts and src files are overwritten)
- Rust (Actix, Axum): `Cargo.toml`, `src/main.rs` (leave these from `cargo new`)
- Java Spring: generally exclude `Makefile` and `merge` only (project content comes from Spring Initializr)
