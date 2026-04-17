FROM mcr.microsoft.com/devcontainers/typescript-node:1-22-bookworm

# Install dev tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        make \
    && rm -rf /var/lib/apt/lists/*
