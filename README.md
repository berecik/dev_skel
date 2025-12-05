# Dev Skel – Multi‑Service Project Skeleton Generator

Dev Skel is a collection of opinionated project skeletons that makes it easy to create **multi‑service projects**.

You start by generating a wrapper project with a backend (Java Spring, FastAPI, or Django). Later you can add more services into the **same project** – for example a React frontend, a Rust Actix service as an authorisation layer, a Rust Axum extra‑fast API, or a Flutter mobile/desktop application – without overwriting what you already have.

Each skeleton ships with best‑practice defaults (tests, linting, Docker build, dev tooling). The `_bin/skel-gen` tool and the main `Makefile` orchestrate how these services are created and wired into a single project directory.

## Core Ideas

- **One project, many services**: A project directory is a **wrapper** that can host multiple services (backend(s), frontend(s), worker APIs, etc.).
- **Service subdirectories**: Each service lives in its own subdirectory inside the wrapper, such as `backend-1/`, `backend-2/`, `frontend-1/`, `actix-api-1/` (names are generated automatically and kept unique).
- **Composable skeletons**: You can mix and match skeletons – e.g. FastAPI or Django backend plus React frontend plus Actix fast API – in one wrapper.
- **Safe re‑generation**: Re‑running a skeleton against an existing wrapper **adds a new service** instead of overwriting an existing one.
- **Common wrapper UX**: The wrapper directory gets a generic `README.md`, `Makefile`, and thin scripts (`./run`, `./test`, `./build`, `./stop`, `./install-deps`, …) that delegate into the selected service.

## Current Capabilities

Today Dev Skel focuses on these building blocks:

### Backends (Python)

- **FastAPI** (`python-fastapi-skel`) – async web API with a DDD‑style layout and automatic OpenAPI docs.
- **Django** (`python-django-skel`) – classic Django backend with batteries included.
- **Flask** (`python-flask-skel`) – lightweight WSGI backend.

### Frontends (TypeScript/JavaScript)

- **React + Vite + TypeScript** (`ts-react-skel`) – modern SPA frontend with Vitest, ESLint, Prettier.
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
# First backend service in a new wrapper (FastAPI)
make gen-fastapi NAME=myproj

# First backend service in a new wrapper (Django)
make gen-django NAME=myproj

# Add a second backend service to the *same* wrapper
# (will auto-pick backend-2 as service directory)
make gen-fastapi NAME=myproj

# Add a React frontend service to the same wrapper
make gen-react NAME=myproj

# Add a Rust Actix quick API to the same wrapper
make gen-actix NAME=myproj
```

### 2) Using `_bin/skel-gen` from anywhere

```bash
_bin/skel-gen <skel_type> <proj_name> [service_in_proj_name]

# Create a new project wrapper with its first FastAPI backend
_bin/skel-gen python-fastapi-skel myproj           # → $PWD/myproj/backend-1/...

# Add another backend service into the same wrapper
_bin/skel-gen python-fastapi-skel myproj           # → $PWD/myproj/backend-2/...

# Add a Django backend service with an explicit name (auto-suffixed if taken)
_bin/skel-gen python-django-skel myproj billing    # → $PWD/myproj/billing/ or billing-1/...

# Add a React frontend service (Vite + React + TS) to the same wrapper
_bin/skel-gen ts-react-skel myproj                 # → $PWD/myproj/frontend-1/...

# Add a Rust Actix quick API service to the same wrapper
_bin/skel-gen rust-actix-skel myproj               # → $PWD/myproj/service-1/...
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
├── _bin/                     # Helper tools (install, update, list, generate, etc.)
├── .editorconfig             # Editor configuration
├── .gitignore                # Git ignore patterns
├── _skels/                   # Skeleton templates
│   ├── python-fastapi-skel/
│   ├── python-flask-skel/
│   ├── python-django-skel/
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

### Create and Test a New Multi‑Service Project (FastAPI + React + Actix)

```bash
# 1) Create wrapper + first backend (FastAPI)
make gen-fastapi NAME=myproj
cd myproj

# This created backend-1/ inside the wrapper
ls
# README.md  Makefile  run  test  build  stop  install-deps  backend-1/

# 2) Add a React frontend as another service
make gen-react NAME=myproj

ls
# README.md  Makefile  run  test  build  stop  install-deps  backend-1/  frontend-1/

# 3) Add a Rust Actix quick API service
make gen-actix NAME=myproj

ls
# ... backend-1/  frontend-1/  service-1/

# 4) Run tests for the currently selected service (via wrapper script)
./test

# 5) Run the dev server (delegates to the inner backend/frontend/run script)
./run dev

# 6) Build and run via Docker (if supported by the active service)
./build
./run docker
```

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
