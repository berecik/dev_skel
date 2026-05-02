# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for Rust Actix Web service
# ---------------------------------------------------------------------------

# -- Stage 1: Build --------------------------------------------------------
FROM rust:1-bookworm AS builder

WORKDIR /build

# Cache dependencies via a dummy build
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -rf src

# Copy real source and build
COPY src/ src/
RUN touch src/main.rs && cargo build --release

# -- Stage 2: Production ---------------------------------------------------
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libssl3 \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --create-home appuser

WORKDIR /app

COPY --from=builder /build/target/release/app .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["./app"]
