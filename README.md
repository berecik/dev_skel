# Dev Skel - Multi-Framework Project Skeleton Generator

A curated collection of production-ready project skeletons for rapid development across multiple languages and frameworks. Generate new projects with best practices, testing infrastructure, and development tooling already configured.

## Features

- **Multiple Framework Support**: 8 different skeleton templates covering popular frameworks
- **Production Ready**: Each skeleton includes testing, linting, and build configuration
- **Rapid Setup**: Generate new projects in seconds with a single command
- **Makefile Automation**: Comprehensive Makefile for project generation and testing
- **Easy Deployment**: Install scripts to sync skeletons to your development directory

## Supported Frameworks

### Python
- **FastAPI** - Modern async web framework with automatic OpenAPI documentation
- **Flask** - Lightweight WSGI web application framework
- **Django** - High-level web framework with batteries included

### JavaScript/TypeScript
- **Vite + React** - Fast modern frontend with TypeScript and React 18
- **Node.js** - JavaScript runtime for backend development

### Java
- **Spring Boot** - Enterprise-grade application framework with Spring ecosystem

### Rust
- **Actix-web** - Powerful, pragmatic, and fast web framework
- **Axum** - Ergonomic and modular web framework built with Tokio

## Quick Start

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

### Install or Update locally

Use the provided helper scripts in `_bin/`:

```bash
# First-time install to your development directory (default: "$HOME/dev_skel")
_bin/install-dev-skel

# Later, to pull updates from this repo into your local installation
_bin/update-dev-skel

# If you keep this repo and your installed copy in sync manually
_bin/sync-dev-skel
```

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
_bin/skel-gen <skel-name> <target-path>

# Examples
_bin/skel-gen python-fastapi-skel ~/work/myapi
_bin/skel-gen ts-react-skel ./frontend
```

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

## Directory Structure

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
│   │   ├── deps              # System dependency installer
│   │   ├── install-deps      # Project dependency installer (copied to generated projects)
│   │   ├── gen               # Project generator
│   │   ├── merge             # File merging script
│   │   ├── test              # Test script (for generated projects)
│   │   ├── test_skel         # Skeleton e2e test script
│   │   ├── build             # Build script (Docker image)
│   │   ├── run               # Run script (dev/prod/docker modes)
│   │   └── stop              # Stop script (stop services)
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

### Create and Test a New FastAPI Project

```bash
# Generate the project
make gen-fastapi NAME=my-api
cd my-api

# Run tests
./test

# Start development server
./run dev

# Or run in Docker
./build
./run docker

# Stop services
./stop
```

### Create a New React Frontend

```bash
# Generate the project
make gen-react NAME=my-frontend
cd my-frontend

# Run tests
./test

# Start development server
./run dev

# Build for production
./build --local

# Or build and run in Docker
./build
./run docker
```

### Generated Project Scripts

Every generated project includes these scripts:

| Script | Description |
|--------|-------------|
| `./test` | Run project tests |
| `./build` | Build Docker image (or local build with `--local`/`--jar`/`--release`) |
| `./run` | Run server (modes: `dev`, `prod`, `docker`) |
| `./stop` | Stop running Docker containers |

Run any script with `-h` or `--help` to see available options.

### Test All Generators

```bash
make test-generators
```

This creates test projects for all frameworks and verifies they build correctly.

## Implementation details (for contributors)

- Each skeleton defines a `merge` script used during generation. Skeleton Makefiles reference it as:
  - `MERGE := $(SKEL_DIR)/merge`
  - `bash $(MERGE) "$(SKEL_DIR)" "$(NAME)"`
- Each skeleton includes:
  - `gen` script: contains ALL generation logic; skeleton Makefiles delegate to it via `bash $(SKEL_DIR)/gen "$(NAME)"`
  - `test` script: end-to-end test that generates into a temp dir and validates the project
- The `_bin/skel-gen` tool prefers a skeleton's `gen` script when present and falls back to `make -C <skel> gen NAME=<target>`.

## License

This project provides skeleton templates for various frameworks. Each generated project may be subject to the license terms of its respective framework and dependencies.
