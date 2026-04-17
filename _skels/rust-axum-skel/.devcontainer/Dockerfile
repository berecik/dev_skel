FROM mcr.microsoft.com/devcontainers/rust:1-bookworm

# Install dev tools and native dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        libssl-dev \
        pkg-config \
        git \
        make \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install cargo-watch for live reloading
RUN cargo install cargo-watch
