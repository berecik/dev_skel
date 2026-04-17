FROM mcr.microsoft.com/devcontainers/javascript-node:1-22-bookworm

# Install dev tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        make \
        postgresql-client \
        python3 \
    && rm -rf /var/lib/apt/lists/*
