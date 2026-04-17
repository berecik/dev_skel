FROM mcr.microsoft.com/devcontainers/go:1-bookworm

# Install dev tools and native dependencies for CGO/sqlite
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libsqlite3-dev \
        git \
        make \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*
