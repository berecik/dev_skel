# FastAPI DDD Project

A production-ready FastAPI project skeleton following Domain-Driven Design (DDD) principles with modern Python tooling.

## Features

- **FastAPI 0.115+** with async support
- **Domain-Driven Design** architecture
- **Python 3.11+** support (3.14 default)
- **uv** for fast package management
- **Docker** multi-stage builds
- **Kubernetes** ready with Helm charts
- **DevContainer** for VS Code
- **PostgreSQL/MySQL** database support
- **Redis** for caching
- **OpenTelemetry** for observability
- **JWT** authentication
- **Health checks** (liveness/readiness probes)

## Quick Start

### Prerequisites

- Python 3.11+ (3.14 default)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Docker (optional)

### Using Scripts (Recommended)

```bash
# Run development server (auto-creates venv if needed)
./run

# Run with Docker Compose
./run compose

# Build Docker image
./build

# Stop all services
./stop
```

### Local Development (Manual)

```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Using Docker

```bash
# Development mode (with hot reload)
./run compose
# or: docker compose up

# Production mode
docker compose --profile production up api-prod

# Build production image
./build
# or: docker build -t myapp:latest --target production .
```

### Using DevContainer (VS Code)

1. Install [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open project in VS Code
3. Click "Reopen in Container" when prompted
4. Wait for container to build and start

## Project Structure

```
├── app/                    # Application layer
│   ├── __init__.py        # FastAPI app factory
│   ├── routes.py          # API route aggregation
│   ├── health.py          # Health check endpoints
│   └── example_items/     # Example domain module
│       ├── models.py      # Domain models
│       ├── routes.py      # API endpoints
│       ├── adapters/      # Data adapters (SQL, etc.)
│       └── tests/         # Module tests
├── core/                   # Core/shared kernel
│   ├── config.py          # Configuration management
│   ├── security.py        # Authentication/authorization
│   ├── repository.py      # Repository pattern base
│   ├── unit_of_work.py    # Unit of Work pattern
│   ├── crud.py            # Generic CRUD operations
│   ├── messagebus.py      # Domain event bus
│   ├── events.py          # Event/Command base classes
│   ├── users/             # User management module
│   └── adapters/          # Core adapters
├── tests/                  # Integration tests
├── k8s/                    # Kubernetes manifests
├── helm/                   # Helm charts
├── .devcontainer/         # DevContainer configuration
├── main.py                # Application entry point
├── config.py              # App configuration
├── pyproject.toml         # Project dependencies
├── Dockerfile             # Multi-stage Docker build
└── docker-compose.yml     # Docker Compose services
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Application
PROJECT_NAME=My FastAPI App
PROJECT_ENV=development      # development, staging, production
DEBUG=True
SECRET_KEY=change-me-in-production

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
# or for MySQL:
# DATABASE_URL=mysql+asyncmy://user:pass@localhost:3306/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# Server
SERVER_HOST=localhost
SERVER_PORT=8000
```

### Database Configuration

See [docs/DATABASE.md](docs/DATABASE.md) for detailed database setup.

## API Documentation

Once running, access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Health Checks

- **Liveness**: `GET /health/liveness` - Is the app running?
- **Readiness**: `GET /health/readiness` - Is the app ready to serve?

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov=core --cov-report=html

# Specific module
pytest app/example_items/tests/
```

### Code Quality

```bash
# Lint and format
ruff check .
ruff format .

# Type checking (optional)
mypy app core
```

### Adding a New Domain Module

1. Create directory under `app/`:
   ```
   app/new_module/
   ├── __init__.py
   ├── models.py
   ├── routes.py
   ├── adapters/
   │   ├── __init__.py
   │   └── sql.py
   └── tests/
   ```

2. Register routes in `app/routes.py`:
   ```python
   from .new_module import routes as new_module_routes
   router.include_router(new_module_routes.router, prefix="/new-module")
   ```

## Scripts

| Script | Description |
|--------|-------------|
| `./run` | Run development server with hot reload |
| `./run prod` | Run production server |
| `./run docker` | Run in Docker container |
| `./run compose` | Run with Docker Compose |
| `./build` | Build production Docker image |
| `./build development` | Build development Docker image |
| `./stop` | Stop all running services |
| `./test` | Run tests |
| `./deps` | Check dependencies |

Use `./run --help`, `./build --help`, or `./stop --help` for more options.

## Documentation

Detailed guides for all aspects of the project:

- [Development Guide](docs/DEVELOPMENT.md) - Setup, workflow, adding features
- [Docker Guide](docs/DOCKER.md) - Docker, Compose, DevContainer
- [Kubernetes Guide](docs/KUBERNETES.md) - K8s, Helm, production deployment
- [Database Guide](docs/DATABASE.md) - PostgreSQL, MySQL, migrations

## License

MIT
