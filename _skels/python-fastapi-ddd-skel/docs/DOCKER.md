# Docker Guide

This guide covers Docker setup, configuration, and best practices for the FastAPI DDD project.

## Table of Contents

- [Overview](#overview)
- [Dockerfile Stages](#dockerfile-stages)
- [Docker Compose](#docker-compose)
- [Development Workflow](#development-workflow)
- [Production Deployment](#production-deployment)
- [DevContainer](#devcontainer)
- [Troubleshooting](#troubleshooting)

## Overview

The project uses a multi-stage Dockerfile optimized for both development and production:

- **Builder stage**: Installs dependencies using `uv`
- **Production stage**: Minimal image with only runtime dependencies
- **Development stage**: Full development environment with hot reload

## Dockerfile Stages

### Building Specific Stages

```bash
# Production image (default)
docker build -t myapp:latest --target production .

# Development image
docker build -t myapp:dev --target development .

# Just the builder (for CI caching)
docker build -t myapp:builder --target builder .
```

### Image Sizes

| Stage | Approximate Size |
|-------|------------------|
| production | ~200MB |
| development | ~400MB |

## Docker Compose

### Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | Development API with hot reload |
| `api-prod` | 8080 | Production API (profile: production) |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache |

### Starting Services

```bash
# Development mode (default)
docker compose up

# With logs in foreground
docker compose up --build

# Detached mode
docker compose up -d

# Production mode
docker compose --profile production up api-prod

# Specific services only
docker compose up api postgres
```

### Stopping Services

```bash
# Stop all
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v

# Stop specific service
docker compose stop api
```

### Viewing Logs

```bash
# All services
docker compose logs

# Follow logs
docker compose logs -f

# Specific service
docker compose logs api

# Last 100 lines
docker compose logs --tail=100 api
```

### Executing Commands

```bash
# Run tests inside container
docker compose exec api pytest

# Open shell
docker compose exec api bash

# Run one-off command
docker compose run --rm api python -c "print('hello')"

# Database migrations
docker compose exec api alembic upgrade head
```

## Development Workflow

### Hot Reload

The development setup mounts your local directory into the container:

```yaml
volumes:
  - .:/app
  - /app/.venv  # Exclude venv from mount
```

Changes to Python files will automatically reload the server.

### Installing New Dependencies

```bash
# Add to pyproject.toml, then:
docker compose exec api uv pip install -e ".[dev]"

# Or rebuild the container
docker compose up --build
```

### Running Tests

```bash
# All tests
docker compose exec api pytest

# With coverage
docker compose exec api pytest --cov=app --cov=core

# Specific test file
docker compose exec api pytest app/example_items/tests/unit/
```

### Database Operations

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U app -d app

# Create migration
docker compose exec api alembic revision --autogenerate -m "add users table"

# Apply migrations
docker compose exec api alembic upgrade head

# Rollback
docker compose exec api alembic downgrade -1
```

## Production Deployment

### Building for Production

```bash
# Build production image
docker build -t myapp:v1.0.0 --target production .

# Tag for registry
docker tag myapp:v1.0.0 registry.example.com/myapp:v1.0.0

# Push to registry
docker push registry.example.com/myapp:v1.0.0
```

### Running in Production

```bash
# Run with environment file
docker run -d \
  --name myapp \
  -p 8000:8000 \
  --env-file .env.production \
  myapp:v1.0.0

# Run with explicit environment variables
docker run -d \
  --name myapp \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/app \
  -e SECRET_KEY=your-secret-key \
  -e PROJECT_ENV=production \
  myapp:v1.0.0
```

### Health Checks

The production image includes a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health/liveness').raise_for_status()"
```

Check container health:

```bash
docker inspect --format='{{.State.Health.Status}}' myapp
```

### Security Best Practices

1. **Non-root user**: The production image runs as `appuser` (UID 1000)
2. **Read-only filesystem**: Use `--read-only` flag with tmpfs for /tmp
3. **No shell**: Consider using `distroless` base for extra security
4. **Secrets**: Never bake secrets into the image

```bash
# Run with read-only filesystem
docker run -d \
  --name myapp \
  --read-only \
  --tmpfs /tmp \
  -p 8000:8000 \
  --env-file .env.production \
  myapp:v1.0.0
```

## DevContainer

### VS Code Setup

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the project folder in VS Code
3. Click "Reopen in Container" in the notification (or use Command Palette: `Dev Containers: Reopen in Container`)

### DevContainer Features

- Python 3.14 (default, supports 3.11+) with uv pre-installed
- PostgreSQL and Redis services
- Pre-configured VS Code extensions:
  - Python
  - Pylance
  - Ruff
  - Docker
  - GitLens
- Automatic port forwarding (8000, 5432, 6379)

### DevContainer Commands

```bash
# Inside devcontainer terminal:

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Connect to database
psql -h postgres -U app -d app
```

### Customizing DevContainer

Edit `.devcontainer/devcontainer.json`:

```json
{
  "customizations": {
    "vscode": {
      "extensions": [
        // Add more extensions here
      ],
      "settings": {
        // Add VS Code settings here
      }
    }
  }
}
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs api

# Check if ports are in use
lsof -i :8000

# Rebuild without cache
docker compose build --no-cache
```

### Database Connection Issues

```bash
# Check if postgres is healthy
docker compose ps

# Test connection from api container
docker compose exec api python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://app:app@postgres:5432/app')
with engine.connect() as conn:
    print('Connected!')
"
```

### Permission Issues

```bash
# Fix ownership of mounted volumes
sudo chown -R $USER:$USER .

# Or run container as current user
docker compose run --user $(id -u):$(id -g) api bash
```

### Slow Builds

Enable BuildKit for faster builds:

```bash
export DOCKER_BUILDKIT=1
docker compose build
```

### Memory Issues

Increase Docker memory limit in Docker Desktop settings, or limit container memory:

```bash
docker run -m 512m myapp:latest
```

## Multi-Architecture Builds

Build for multiple architectures:

```bash
# Create builder
docker buildx create --name mybuilder --use

# Build and push multi-arch image
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t registry.example.com/myapp:v1.0.0 \
  --push \
  --target production \
  .
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    target: production
    push: true
    tags: myapp:${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### GitLab CI Example

```yaml
build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA --target production .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```
