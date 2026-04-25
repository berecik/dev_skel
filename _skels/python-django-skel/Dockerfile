# syntax=docker/dockerfile:1
#
# Django Project Dockerfile
# Supports Python 3.11+, default: 3.14
# To use different version: docker build --build-arg PYTHON_VERSION=3.13 .

ARG PYTHON_VERSION=3.14

# Build stage - uses uv for fast package installation
FROM python:${PYTHON_VERSION}-slim AS builder

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy project metadata and source (needed for editable install)
COPY pyproject.toml .
COPY app/ app/
COPY myproject/ myproject/
COPY tests/ tests/
COPY manage.py conftest.py ./

# Install dependencies with uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --target=/app/deps -e ".[dev]"

# Production stage
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim AS production

ARG PROJECT_ENV="production"
ARG PYTHON_VERSION=3.14

EXPOSE 8000

ENV PROJECT_ENV=${PROJECT_ENV} \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Install runtime dependencies only
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
# Note: Python version in path must match PYTHON_VERSION
COPY --from=builder /app/deps /usr/local/lib/python${PYTHON_VERSION}/site-packages

# Copy application code
COPY --from=builder /app/app ./app
COPY --from=builder /app/myproject ./myproject
COPY --from=builder /app/manage.py /app/conftest.py ./

# Copy .env.example as fallback
COPY .env.example .env.example

ENV PYTHONPATH="/app"

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Development stage
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim AS development

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PROJECT_ENV="development" \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=0 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Install dev dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev gcc git curl make && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and source (needed for editable install)
COPY pyproject.toml .
COPY app/ app/
COPY myproject/ myproject/
COPY tests/ tests/
COPY manage.py conftest.py ./

# Install Python dependencies with uv (including dev extras)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e ".[dev]"

ENV PYTHONPATH="/app"

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
