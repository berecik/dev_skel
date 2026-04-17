# Dev Container Dockerfile
# Supports Python 3.11+, default: 3.14
# Available versions: mcr.microsoft.com/devcontainers/python:1-3.11-bookworm, 3.12, 3.13, 3.14

ARG PYTHON_VERSION=3.14
FROM mcr.microsoft.com/devcontainers/python:1-${PYTHON_VERSION}-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        git \
        curl \
        make \
        postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=0 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install Python dependencies from pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv pip install --system -e ".[dev]"

# Create non-root user (already exists in devcontainer base image)
USER vscode
