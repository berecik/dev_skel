# Skeleton Templates Reference

## Overview

Each skeleton is a complete, working project template that can be used to bootstrap new projects. Skeletons include:
- Source code with example implementations
- Configuration files
- Test setup
- Development tooling

## Python Skeletons

### python-fastapi-skel

**Location**: `_skels/python-fastapi-skel/`

**Framework**: FastAPI with async SQLAlchemy

**Structure**:
```
python-fastapi-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # Pydantic settings
│   ├── database.py      # Async SQLAlchemy setup
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   └── routes.py        # API routes
└── tests/
    ├── __init__.py
    └── test_main.py
```

**Dependencies Installed**:
- fastapi
- uvicorn
- sqlalchemy
- aiosqlite
- pydantic-settings
- alembic
- python-dotenv

**Generated Project Usage**:
```bash
cd myapp
source .venv/bin/activate
uvicorn app.main:app --reload
```

---

### python-flask-skel

**Location**: `_skels/python-flask-skel/`

**Framework**: Flask with Flask-SQLAlchemy

**Structure**:
```
python-flask-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── run.py               # Entry point
├── app/
│   ├── __init__.py      # Flask app factory
│   ├── config.py        # Configuration
│   ├── models.py        # SQLAlchemy models
│   └── routes.py        # Blueprint routes
└── tests/
    ├── __init__.py
    └── test_routes.py
```

**Dependencies Installed**:
- flask
- flask-sqlalchemy
- flask-migrate
- python-dotenv
- gunicorn

**Generated Project Usage**:
```bash
cd myapp
source .venv/bin/activate
python run.py
# or: flask run
```

---

### python-django-skel

**Location**: `_skels/python-django-skel/`

**Framework**: Django

**Structure**:
```
python-django-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── conftest.py          # pytest configuration
├── manage.py
├── myproject/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── tests/
    ├── __init__.py
    └── test_views.py
```

**Dependencies Installed**:
- django
- python-dotenv
- gunicorn

**Generation Notes**:
- Uses `django-admin startproject` then overlays skeleton files
- Replaces default `urls.py` with skeleton version

**Generated Project Usage**:
```bash
cd myapp
source .venv/bin/activate
python manage.py runserver
```

---

## TypeScript/JavaScript Skeletons

### ts-vite-react-skel

**Location**: `_skels/ts-vite-react-skel/`

**Framework**: Vite + React + TypeScript + Vitest

**Structure**:
```
ts-vite-react-skel/
├── Makefile
├── .env.example
├── .gitignore
├── index.html
├── vite.config.ts       # Vite + Vitest config
├── tsconfig.node.json   # TypeScript config for Vite
├── eslint.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── App.css
│   ├── App.test.tsx
│   ├── index.css
│   ├── vite-env.d.ts
│   ├── setupTests.ts    # Vitest setup
│   ├── components/
│   │   └── .gitkeep
│   └── hooks/
│       └── .gitkeep
└── (node_modules, package.json - not copied)
```

**Dependencies Installed** (by generator):
- vite (via `npm create vite@latest`)
- vitest
- @testing-library/react
- @testing-library/jest-dom
- jsdom

**Generation Notes**:
- Uses `npm create vite@latest` to scaffold base project
- Removes generated `vite.config.ts` and `tsconfig.node.json`
- Copies skeleton versions with Vitest configuration
- Excludes `package.json`, `package-lock.json`, `tsconfig.json` from merge

**Generated Project Usage**:
```bash
cd myapp
npm run dev      # Development server
npm run build    # Production build
npm test         # Run tests
```

---

### js-skel

**Location**: `_skels/js-skel/`

**Framework**: Plain JavaScript/Node.js

**Structure**:
```
js-skel/
├── Makefile
├── .gitignore
├── .editorconfig
├── .prettierrc
├── eslint.config.js
├── src/
│   ├── index.js
│   └── index.test.js
└── (node_modules, package-lock.json - copied)
```

**Generation Notes**:
- Uses `npm init -y` to create package.json
- Copies skeleton files
- Runs `npm install`

**Generated Project Usage**:
```bash
cd myapp
node src/index.js
npm test
```

---

## Java Skeletons

### java-spring-skel

**Location**: `_skels/java-spring-skel/`

**Framework**: Spring Boot

**Structure**:
```
java-spring-skel/
├── Makefile
├── .env.example
├── .gitignore
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/example/skel/
│   │   │   ├── Application.java
│   │   │   ├── controller/
│   │   │   │   ├── RootController.java
│   │   │   │   └── ItemController.java
│   │   │   ├── model/
│   │   │   │   └── Item.java
│   │   │   ├── repository/
│   │   │   │   └── ItemRepository.java
│   │   │   └── service/
│   │   │       └── ItemService.java
│   │   └── resources/
│   │       ├── application.properties
│   │       └── application-prod.properties
│   └── test/java/com/example/skel/
│       ├── ApplicationTests.java
│       └── controller/
│           └── ItemControllerTest.java
└── (target/ - not copied)
```

**Dependencies** (from pom.xml):
- Spring Boot Starter Web
- Spring Boot Starter Data JPA
- H2 Database
- Spring Boot Starter Test

**Generation Notes**:
- Simply copies all skeleton files
- Runs `mvn dependency:resolve`

**Generated Project Usage**:
```bash
cd myapp
mvn spring-boot:run
mvn test
```

---

## Rust Skeletons

### rust-actix-skel

**Location**: `_skels/rust-actix-skel/`

**Framework**: Actix-web

**Structure**:
```
rust-actix-skel/
├── Makefile
├── .env.example
├── Cargo.toml
├── Cargo.lock
└── src/
    └── main.rs
```

**Dependencies** (from Cargo.toml):
- actix-web
- actix-rt
- serde (with derive)
- tokio

**Generation Notes**:
- Uses `cargo new` to create base project
- Removes generated `Cargo.toml` and `src/main.rs`
- Copies skeleton versions
- Runs `cargo fetch`

**Generated Project Usage**:
```bash
cd myapp
cargo run
cargo test
```

---

### rust-axum-skel

**Location**: `_skels/rust-axum-skel/`

**Framework**: Axum

**Structure**:
```
rust-axum-skel/
├── Makefile
├── .env.example
├── Cargo.toml
├── Cargo.lock
├── rustfmt.toml
└── src/
    └── main.rs
```

**Dependencies** (from Cargo.toml):
- axum
- tokio (full features)
- serde (with derive)
- tower

**Generation Notes**:
- Uses `cargo new` to create base project
- Removes generated `Cargo.toml` and `src/main.rs`
- Copies skeleton versions
- Runs `cargo fetch`

**Generated Project Usage**:
```bash
cd myapp
cargo run
cargo test
```

---

## merge_skel Exclusions

All skeleton Makefiles use a `merge_skel` macro that excludes these patterns:

**Directories**:
- `.venv/`
- `node_modules/`
- `target/`
- `__pycache__/`
- `.git/`
- `dist/`
- `build/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `*.egg-info/`

**Files**:
- `*.pyc`, `*.pyo`
- `*.class`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `Makefile`

**Framework-specific exclusions** (ts-vite-react-skel):
- `package.json`
- `package-lock.json`
- `tsconfig.json`
