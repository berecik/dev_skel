FROM mcr.microsoft.com/devcontainers/java:1-21-bookworm

# Install Maven and dev tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        maven \
        git \
        make \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*
