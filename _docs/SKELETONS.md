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
- **Testing**
  - From skeleton dir: `make test` which runs `bash ./test`
  - Each `test` script generates into a temporary directory, runs the tests, and performs a non-interactive run/build check
- **Merge script**
  - Each skeleton uses an executable `merge` script referenced by its Makefile as `MERGE := $(SKEL_DIR)/merge`
  - It copies auxiliary files into the generated project without overwriting generator-owned files

## Available Skeletons

### Python

- [python-fastapi-skel](./python-fastapi-skel.md) - FastAPI with async SQLAlchemy
- [python-flask-skel](./python-flask-skel.md) - Flask with Flask-SQLAlchemy
- [python-django-skel](./python-django-skel.md) - Django

### TypeScript/JavaScript

- [ts-vite-react-skel](./ts-vite-react-skel.md) - Vite + React + TypeScript + Vitest
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
- TS Vite React: `package.json`, `package-lock.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts`
- Rust (Actix, Axum): `Cargo.toml`, `src/main.rs` (leave these from `cargo new`)
- Java Spring: generally exclude `Makefile` and `merge` only (project content comes from Spring Initializr)
