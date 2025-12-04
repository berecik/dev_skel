# Developer Projects - Skeleton Generator

A Makefile-based project generator system that creates new projects from skeleton templates. Supports multiple languages and frameworks including Python (FastAPI, Flask, Django), TypeScript (Vite+React), JavaScript (Node.js), Java (Spring Boot), and Rust (Actix-web, Axum).

## Directory Structure

```
.
├── Makefile              # Main orchestration Makefile
├── _skels/               # Skeleton templates directory
│   ├── python-fastapi-skel/
│   ├── python-flask-skel/
│   ├── python-django-skel/
│   ├── ts-vite-react-skel/
│   ├── js-skel/
│   ├── java-spring-skel/
│   ├── rust-actix-skel/
│   └── rust-axum-skel/
├── _docs/                # Documentation
│   ├── README.md         # This file
│   ├── MAKEFILE.md       # Main Makefile documentation
│   ├── SKELETONS.md      # Skeleton details
│   └── LLM-MAINTENANCE.md # LLM maintenance guide
└── _test_projects/       # Generated test projects (gitignored)
```

## Quick Start

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

- [Makefile Reference](MAKEFILE.md) - Detailed documentation of the main Makefile
- [Skeleton Templates](SKELETONS.md) - Details about each skeleton template
- [LLM Maintenance Guide](LLM-MAINTENANCE.md) - Instructions for AI assistants maintaining this project

## Requirements

- **Python**: Python 3.11+ with venv
- **Node.js**: Node.js 20+ with npm
- **Java**: JDK 21+ with Maven
- **Rust**: Stable Rust with Cargo
- **Make**: GNU Make 4.0+
