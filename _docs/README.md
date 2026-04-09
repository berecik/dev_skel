# Developer Projects – Multi‑Service Skeleton Generator

A Makefile-based project generator system that creates **multi‑service projects** from reusable skeleton templates.

You can start a project with a backend (Java Spring, FastAPI, or Django) and then add more services into the **same wrapper directory** – for example a React frontend, a Rust Actix service as an authorisation layer, a Rust Axum extra‑fast API, or a Flutter mobile/desktop application – without overwriting existing code. The `_bin/skel-gen` tool takes care of creating unique service subdirectories (like `backend-1/`, `frontend-1/`, `service-1/`, …) inside one project.

## Directory Structure

```
.
├── Makefile              # Main orchestration Makefile
├── skel-deps             # Dependency installer for all skeletons
├── maintenance           # One-shot maintenance test runner (make clean-test, make test-generators, ./test)
├── test                  # Root script that runs all skeleton e2e tests
├── _bin/                 # Helper tools
├── _skels/               # Skeleton templates directory
│   ├── python-fastapi-skel/
│   ├── python-flask-skel/
│   ├── python-django-skel/
│   ├── python-django-bolt-skel/
│   ├── ts-react-skel/
│   ├── js-skel/
│   ├── java-spring-skel/
│   ├── rust-actix-skel/
│   └── rust-axum-skel/
├── _docs/                # Documentation
│   ├── README.md         # This file
│   ├── DEPENDENCIES.md   # Dependency installation guide
│   ├── MAKEFILE.md       # Main Makefile documentation
│   ├── SKELETONS.md      # Skeleton details
│   └── LLM-MAINTENANCE.md # LLM maintenance guide
└── _test_projects/       # Generated test projects (gitignored)
```

## Quick Start

### Install System Dependencies

Install required dependencies for all frameworks or specific ones:

```bash
# List all available skeletons
./skel-deps --list

# Install all dependencies
./skel-deps --all

# Install for specific framework
./skel-deps java-spring-skel
./skel-deps python-django
```

Supported: macOS (Homebrew), Ubuntu/Debian (apt), Arch Linux (pacman), Fedora/RHEL (dnf)

See [DEPENDENCIES.md](DEPENDENCIES.md) for detailed information.

### Generate a New Project (Wrapper + Services)

There are two equivalent ways to generate services:

1. From the repo root via the main Makefile targets.
2. From anywhere using the relocatable `_bin/skel-gen` tool.

```bash
# First backend service in a new wrapper (FastAPI)
make gen-fastapi NAME=myproj

# First backend service in a new wrapper (Django)
make gen-django NAME=myproj

# Add a second backend service to the *same* wrapper
make gen-fastapi NAME=myproj

# Add a React frontend service to the same wrapper
make gen-react NAME=myproj

# Add a Rust Actix quick API to the same wrapper
make gen-actix NAME=myproj
```

2) With the generator tool (relocatable) from anywhere

```bash
_bin/skel-gen <skel_type> <proj_name> [service_in_proj_name]

# Create a new project wrapper with its first FastAPI backend
_bin/skel-gen python-fastapi-skel myproj           # → $PWD/myproj/backend-1/...

# Add another backend service into the same wrapper
_bin/skel-gen python-fastapi-skel myproj           # → $PWD/myproj/backend-2/...

# Add a React frontend service
_bin/skel-gen ts-react-skel myproj                 # → $PWD/myproj/frontend-1/...

# Add a Rust Actix quick API service
_bin/skel-gen rust-actix-skel myproj               # → $PWD/myproj/service-1/...
```

Parameters:

- `skel_type` – skeleton directory name under `_skels/` (for example `python-fastapi-skel`, `ts-react-skel`).
- `proj_name` – **leaf** wrapper directory name (no `/`), created under the current working directory.
- `service_in_proj_name` – optional **service directory base name** inside the wrapper. If omitted, a generic base is used per skeleton (`backend`, `frontend`, or `service`). Dev Skel automatically appends numeric suffixes (`-1`, `-2`, …) so that service directory names are unique.

### Generated Project Layout

Every generator treats the user-provided path as a **wrapper directory** (`main_dir`) and creates the real framework-specific project inside one or more **service subdirectories** (`project_dir`) inside `main_dir`.

Typical service directories:

- Python backends (FastAPI, Flask, Django): `backend-1/`, `backend-2/`, …
- React frontend (ts-react-skel): `frontend-1/`, `frontend-2/`, …
- Node.js (js-skel): `service-1/` or `app-1/`
- Java Spring / Rust services: `service-1/`, `service-2/`, …

Example (FastAPI + React + Actix):

```text
myproj/
  README.md      # generic wrapper README
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts (forward into a chosen service)
  backend-1/     # real FastAPI backend
  frontend-1/    # real React frontend
  service-1/     # real Rust Actix quick API
```

Wrapper-level scripts like `./run`, `./test`, `./build`, `./stop` live in `main_dir` and **forward all arguments** to the scripts in a selected `project_dir`.

### Install Project Dependencies

After generating a project, install its dependencies using the included `install-deps` script from the wrapper directory:

```bash
# Generate a project
make gen-fastapi NAME=myapp
cd myapp

# Install project dependencies (delegates into backend/install-deps)
./install-deps

# For Python projects, activate the virtual environment from project_dir
cd backend
source .venv/bin/activate

# Start development
uvicorn app.main:app --reload
```

Each generated project includes an `install-deps` script (in `project_dir`, plus a wrapper in `main_dir`) that:
- **Python projects**: Creates virtual environment, installs from requirements.txt
- **Node.js projects**: Runs npm install
- **Java projects**: Runs Maven dependency resolution and installation
- **Rust projects**: Runs cargo fetch and build

See [DEPENDENCIES.md](DEPENDENCIES.md) for more information.

### Test All Generators

```bash
make test-generators
```

This creates wrapper+inner projects under `_test_projects/` and performs basic import/build checks inside the appropriate `project_dir` (for example, `backend/`, `frontend/`, `service/`).

### Run Skeleton E2E Tests and Maintenance Suite

- Run all skeleton E2E tests:

  ```bash
  ./test
  ```

  This calls each skeleton's `test_skel` script, which generates a temporary project using the wrapper layout and runs its tests plus Docker build checks.

- Run the full maintenance workflow (used by CI):

  ```bash
  ./maintenance
  ```

  This executes:
  - `make clean-test`
  - `make test-generators`
  - `./test`

  The GitHub Actions workflow `.github/workflows/maintenance.yml` runs this same script on pushes and pull requests to `master`.

### Show Available Commands

```bash
make help
```

## Documentation Index

- [Dependencies](DEPENDENCIES.md) - System dependency installation guide for all platforms
- [Makefile Reference](MAKEFILE.md) - Detailed documentation of the main Makefile
- [Skeleton Templates](SKELETONS.md) - Details about each skeleton template
- [LLM Maintenance Guide](LLM-MAINTENANCE.md) - Instructions for AI assistants maintaining this project

## Requirements

Each framework has specific requirements. Use `./skel-deps` to install them automatically:

- **Python**: Python 3.10+ with pip and venv
- **Node.js**: Node.js 20+ with npm
- **Java**: JDK 21+ with Maven
- **Rust**: Stable Rust with Cargo (via rustup)
- **Make**: GNU Make 4.0+

Run `./skel-deps --all` to install all dependencies. See [DEPENDENCIES.md](DEPENDENCIES.md) for details.
