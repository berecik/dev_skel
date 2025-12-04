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

### Installation

Install dev_skel to your development directory:

```bash
./install.sh
```

This copies all skeleton templates to `~/dev/` (excludes test projects and scripts).

### Update Existing Installation

Sync updates from dev_skel to your installation:

```bash
./update.sh
```

### Generate a New Project

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

## Makefile Commands

### Project Generation
- `make gen-<framework> NAME=myapp` - Generate a new project from a skeleton

### Testing
- `make test-generators` - Test all skeleton generators
- `make test-all` - Run tests for all skeleton projects
- `make test-<framework>` - Run tests for a specific skeleton

### Maintenance
- `make list` - List all available skeletons
- `make status` - Show status of all skeleton directories
- `make clean-all` - Clean all skeleton projects
- `make help` - Show all available commands

## Directory Structure

```
dev_skel/
├── Makefile                  # Main orchestration Makefile
├── install.sh                # Install skeletons to ~/dev
├── update.sh                 # Update ~/dev from dev_skel
├── .editorconfig             # Editor configuration
├── .gitignore                # Git ignore patterns
├── _skels/                   # Skeleton templates
│   ├── python-fastapi-skel/
│   ├── python-flask-skel/
│   ├── python-django-skel/
│   ├── ts-vite-react-skel/
│   ├── js-skel/
│   ├── java-spring-skel/
│   ├── rust-actix-skel/
│   └── rust-axum-skel/
└── _docs/                    # Documentation
    ├── README.md
    ├── MAKEFILE.md
    ├── SKELETONS.md
    └── LLM-MAINTENANCE.md
```

## Requirements

Each framework has specific requirements:

- **Python**: Python 3.10+ with venv
- **Node.js**: Node.js 18+ with npm
- **Java**: JDK 17+ with Maven
- **Rust**: Rust 1.70+ with Cargo
- **Make**: GNU Make 4.0+

## Documentation

Detailed documentation is available in the `_docs/` directory:

- [Makefile Reference](_docs/MAKEFILE.md) - Complete documentation of all Makefile targets
- [Skeleton Templates](_docs/SKELETONS.md) - Detailed information about each skeleton
- [LLM Maintenance Guide](_docs/LLM-MAINTENANCE.md) - Guide for AI assistants maintaining this project

## Common Workflows

### Create and Test a New FastAPI Project

```bash
make gen-fastapi NAME=my-api
cd my-api
source .venv/bin/activate
pytest
uvicorn app.main:app --reload
```

### Create a New React Frontend

```bash
make gen-vite-react NAME=my-frontend
cd my-frontend
npm run dev
```

### Test All Generators

```bash
make test-generators
```

This creates test projects for all frameworks and verifies they build correctly.

## License

This project provides skeleton templates for various frameworks. Each generated project may be subject to the license terms of its respective framework and dependencies.
