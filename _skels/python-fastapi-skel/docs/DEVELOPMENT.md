# Development Guide

This guide covers setting up the development environment, coding standards, and workflow for the FastAPI DDD project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Project Architecture](#project-architecture)
- [Development Workflow](#development-workflow)
- [Adding New Features](#adding-new-features)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Debugging](#debugging)
- [IDE Configuration](#ide-configuration)

## Prerequisites

### Required

- Python 3.11+ (3.14 default)
- Git

### Recommended

- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- Docker & Docker Compose
- VS Code with Dev Containers extension

### Installing uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify installation
uv --version
```

## Environment Setup

### Option 1: Local Development

```bash
# Clone the project
git clone <repository-url>
cd project-name

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies with uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Start PostgreSQL and Redis (Docker)
docker compose up -d postgres redis

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Docker Compose

```bash
# Start all services with hot reload
docker compose up

# Or in detached mode
docker compose up -d

# View logs
docker compose logs -f api
```

### Option 3: VS Code DevContainer

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the project folder
3. Click "Reopen in Container" when prompted
4. Wait for the container to build

The DevContainer includes:
- Python 3.14 with uv (configurable to 3.11+)
- PostgreSQL and Redis services
- Pre-configured VS Code extensions
- Automatic port forwarding

## Project Architecture

### Domain-Driven Design Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                       │
│                    (FastAPI Routes/Endpoints)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                        │
│              (Use Cases, Commands, Queries)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Domain Layer                            │
│         (Entities, Value Objects, Domain Events)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                       │
│            (Repositories, External Services)                  │
└─────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
├── app/                       # Application modules
│   ├── __init__.py           # FastAPI app factory
│   ├── routes.py             # Route aggregation
│   ├── health.py             # Health check endpoints
│   └── example_items/        # Example domain module
│       ├── __init__.py
│       ├── models.py         # Domain models (entities, value objects)
│       ├── routes.py         # API endpoints
│       ├── schemas.py        # Pydantic schemas (DTOs)
│       ├── services.py       # Application services
│       ├── adapters/         # Infrastructure adapters
│       │   ├── __init__.py
│       │   └── sql.py        # SQLAlchemy repository
│       └── tests/            # Module tests
│           ├── unit/
│           └── integration/
├── core/                      # Shared kernel
│   ├── config.py             # Configuration management
│   ├── security.py           # Authentication/authorization
│   ├── repository.py         # Repository pattern base
│   ├── unit_of_work.py       # Unit of Work pattern
│   ├── crud.py               # Generic CRUD operations
│   ├── messagebus.py         # Domain event bus
│   ├── events.py             # Event/Command base classes
│   └── adapters/             # Core adapters
├── tests/                     # Integration tests
├── main.py                    # Application entry point
└── config.py                  # App configuration
```

### Key Patterns

#### Repository Pattern

```python
# core/repository.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")

class AbstractRepository(ABC, Generic[T]):
    @abstractmethod
    async def add(self, entity: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def get(self, id: int) -> T | None:
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> list[T]:
        raise NotImplementedError
```

#### Unit of Work Pattern

```python
# core/unit_of_work.py
from abc import ABC, abstractmethod

class AbstractUnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self):
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, *args):
        raise NotImplementedError

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError
```

#### Domain Events

```python
# core/events.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Event:
    """Base class for domain events"""
    occurred_at: datetime = None

    def __post_init__(self):
        if self.occurred_at is None:
            self.occurred_at = datetime.utcnow()

@dataclass
class ItemCreated(Event):
    item_id: int
    name: str
```

## Development Workflow

### Daily Workflow

```bash
# 1. Pull latest changes
git pull origin main

# 2. Start services
docker compose up -d postgres redis

# 3. Activate environment
source .venv/bin/activate

# 4. Run migrations (if any)
alembic upgrade head

# 5. Start development server
uvicorn main:app --reload

# 6. Run tests before committing
pytest

# 7. Format and lint
ruff check --fix .
ruff format .
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/add-user-profiles

# Make changes and commit
git add .
git commit -m "Add user profile endpoints"

# Push and create PR
git push -u origin feature/add-user-profiles
```

### Commit Message Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Example:
```
feat(users): add user profile endpoints

- Add GET /users/{id}/profile endpoint
- Add PUT /users/{id}/profile endpoint
- Add profile image upload

Closes #123
```

## Adding New Features

### Step 1: Create Domain Module

```bash
mkdir -p app/users/{adapters,tests/unit,tests/integration}
touch app/users/{__init__,models,routes,schemas,services}.py
touch app/users/adapters/{__init__,sql}.py
```

### Step 2: Define Domain Models

```python
# app/users/models.py
from sqlmodel import SQLModel, Field
from datetime import datetime

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Step 3: Create Schemas (DTOs)

```python
# app/users/schemas.py
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
```

### Step 4: Implement Repository

```python
# app/users/adapters/sql.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.repository import AbstractRepository
from ..models import User

class UserRepository(AbstractRepository[User]):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def get(self, id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
```

### Step 5: Create API Routes

```python
# app/users/routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import UserCreate, UserRead
from .adapters.sql import UserRepository
from core.adapters.sql import get_session

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    # Check if user exists
    existing = await repo.get_by_email(user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    # Create user
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
    )
    user = await repo.add(user)
    await session.commit()
    return user

@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    user = await repo.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
```

### Step 6: Register Routes

```python
# app/routes.py
from fastapi import APIRouter
from .users import routes as user_routes

router = APIRouter()
router.include_router(user_routes.router)
```

### Step 7: Create Migration

```bash
alembic revision --autogenerate -m "add users table"
alembic upgrade head
```

### Step 8: Write Tests

```python
# app/users/tests/unit/test_models.py
import pytest
from app.users.models import User

def test_user_creation():
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        full_name="Test User",
    )
    assert user.email == "test@example.com"
    assert user.is_active is True


# app/users/tests/integration/test_routes.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post(
        "/users/",
        json={
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
```

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov=core --cov-report=html

# Specific module
pytest app/users/tests/

# Specific test file
pytest app/users/tests/unit/test_models.py

# Specific test
pytest app/users/tests/unit/test_models.py::test_user_creation

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf
```

### Test Configuration

```python
# conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from core.adapters.sql import Base, get_session

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(db_engine):
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

### Test Categories

```bash
# Unit tests only
pytest app/*/tests/unit/

# Integration tests only
pytest app/*/tests/integration/

# Mark-based selection
pytest -m "slow"
pytest -m "not slow"
```

## Code Quality

### Ruff (Linting & Formatting)

```bash
# Check for issues
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Format code
ruff format .

# Check formatting (CI)
ruff format --check .
```

### Configuration

```toml
# pyproject.toml
[tool.ruff]
target-version = "py314"  # default version (supports 3.11+)
line-length = 88

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["app", "core"]
```

### Type Checking (Optional)

```bash
# Install mypy
uv pip install mypy

# Run type checker
mypy app core
```

### Pre-commit Hooks

```bash
# Install pre-commit
uv pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

## Debugging

### VS Code Debugging

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "${file}"],
      "justMyCode": false
    }
  ]
}
```

### Interactive Debugging

```python
# Using breakpoint() (Python 3.7+)
def my_function():
    x = calculate_something()
    breakpoint()  # Drops into pdb
    return x

# Using ipdb (if installed)
import ipdb; ipdb.set_trace()
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# In your code
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

Configure in `.env`:
```bash
LOG_LEVEL=DEBUG
```

## IDE Configuration

### VS Code

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["."]
}
```

### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable pytest as test runner
3. Configure Ruff as external tool:
   - Program: `ruff`
   - Arguments: `check --fix $FilePath$`
   - Working directory: `$ProjectFileDir$`

## Performance Tips

### Database Queries

```python
# Use selectinload for relationships
from sqlalchemy.orm import selectinload

query = select(User).options(selectinload(User.items))

# Use pagination
query = select(User).offset(skip).limit(limit)
```

### Async Best Practices

```python
# Good: Run independent operations concurrently
import asyncio

async def get_dashboard_data(user_id: int):
    profile, stats, notifications = await asyncio.gather(
        get_profile(user_id),
        get_stats(user_id),
        get_notifications(user_id),
    )
    return {"profile": profile, "stats": stats, "notifications": notifications}

# Bad: Sequential when not needed
async def get_dashboard_data_slow(user_id: int):
    profile = await get_profile(user_id)
    stats = await get_stats(user_id)
    notifications = await get_notifications(user_id)
    return {"profile": profile, "stats": stats, "notifications": notifications}
```

### Caching

```python
from functools import lru_cache
import redis.asyncio as redis

# Simple in-memory cache
@lru_cache(maxsize=100)
def get_settings():
    return load_settings_from_db()

# Redis cache
redis_client = redis.from_url("redis://localhost:6379")

async def get_cached_data(key: str):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    data = await fetch_data()
    await redis_client.setex(key, 3600, json.dumps(data))
    return data
```
