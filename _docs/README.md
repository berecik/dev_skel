# Developer Projects - Skeleton Generator

A Makefile-based project generator system that creates new projects from skeleton templates. Supports multiple languages and frameworks including Python (FastAPI, Flask, Django), TypeScript (Vite+React), JavaScript (Node.js), Java (Spring Boot), and Rust (Actix-web, Axum).

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

### Generate a New Project

Two equivalent ways:

1) From the repo root via the main Makefile targets

```bash
# Python FastAPI
make gen-fastapi NAME=myapp

# Python Flask
make gen-flask NAME=myapp

# Python Django
make gen-django NAME=myapp

# TypeScript React+Vite
make gen-react NAME=myapp

# JavaScript/Node.js
make gen-js NAME=myapp

# Java Spring Boot
make gen-spring NAME=myapp

# Rust Actix-web
make gen-actix NAME=myapp

# Rust Axum
make gen-axum NAME=myapp
```

2) With the generator tool (relocatable) from anywhere

```bash
_bin/skel-gen <skel_type> <proj_name> [service_in_proj_name]

# Examples
_bin/skel-gen python-fastapi-skel my-api            # → $PWD/my-api/backend/...
_bin/skel-gen python-fastapi-skel my-api api       # → $PWD/my-api/api/...
_bin/skel-gen ts-react-skel frontend               # → $PWD/frontend/frontend/...
_bin/skel-gen ts-react-skel frontend ui            # → $PWD/frontend/ui/...
```

Parameters:

- `skel_type` – skeleton directory name under `_skels/` (for example `python-fastapi-skel`, `ts-react-skel`).
- `proj_name` – **leaf** directory name (no `/`), created under the current working directory.
- `service_in_proj_name` – optional inner service directory name; if omitted, each skeleton uses its historical default (`backend`, `service`, `app`, `frontend`, etc.).

### Generated Project Layout

Every generator treats the user-provided path as a **wrapper directory** (`main_dir`) and creates the real framework-specific project inside a **project subdirectory** (`project_dir`) derived from the skeleton:

- Python backends (FastAPI, Flask, Django): `backend/`
- React frontend (ts-react-skel): `frontend/`
- Node.js (js-skel): `app/`
- Java Spring / Rust services: `service/`

Example (FastAPI):

```text
my-api/
  README.md      # generic wrapper README
  Makefile       # generic wrapper Makefile
  run test ...   # thin wrapper scripts
  backend/       # real FastAPI project
```

Wrapper-level scripts like `./run`, `./test`, `./build`, `./stop` live in `main_dir` and **forward all arguments** to the corresponding scripts in `project_dir`.

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
