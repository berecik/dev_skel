# Developer Projects - Skeleton Generator

A Makefile-based project generator system that creates new projects from skeleton templates. Supports multiple languages and frameworks including Python (FastAPI, Flask, Django), TypeScript (Vite+React), JavaScript (Node.js), Java (Spring Boot), and Rust (Actix-web, Axum).

## Directory Structure

```
.
├── Makefile              # Main orchestration Makefile
├── skel-deps             # Dependency installer for all skeletons
├── _bin/                 # Helper tools
├── _skels/               # Skeleton templates directory
│   ├── python-fastapi-skel/
│   │   ├── deps          # System dependency installer
│   │   ├── install-deps  # Project dependency installer (copied to generated projects)
│   │   ├── gen           # Project generator
│   │   ├── merge         # File merger
│   │   └── test          # Test script
│   ├── python-flask-skel/
│   ├── python-django-skel/
│   ├── ts-vite-react-skel/
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

# TypeScript Vite+React
make gen-vite-react NAME=myapp

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
_bin/skel-gen ts-vite-react-skel ./frontend
```

### Install Project Dependencies

After generating a project, install its dependencies using the included `install-deps` script:

```bash
# Generate a project
make gen-fastapi NAME=myapp
cd myapp

# Install project dependencies
./install-deps

# For Python projects, activate the virtual environment
source .venv/bin/activate

# Start development
uvicorn app.main:app --reload
```

Each generated project includes an `install-deps` script that:
- **Python projects**: Creates virtual environment, installs from requirements.txt
- **Node.js projects**: Runs npm install
- **Java projects**: Runs Maven dependency resolution and installation
- **Rust projects**: Runs cargo fetch and build

See [DEPENDENCIES.md](DEPENDENCIES.md) for more information.

### Test All Generators

```bash
make test-generators
```

### Run a skeleton's E2E tests

```bash
# From the skeleton directory
cd _skels/python-fastapi-skel
make test   # calls: bash ./test
```

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
