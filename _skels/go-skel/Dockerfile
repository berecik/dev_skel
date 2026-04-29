# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for Go service
# ---------------------------------------------------------------------------

# -- Stage 1: Build --------------------------------------------------------
FROM golang:1.23-bookworm AS builder

WORKDIR /build

# Cache dependencies first
COPY go.mod go.sum ./
RUN go mod download

# Copy source and build (CGO_ENABLED=1 for sqlite support)
COPY . .
RUN CGO_ENABLED=1 go build -o app .

# -- Stage 2: Production ---------------------------------------------------
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --create-home appuser

WORKDIR /app

COPY --from=builder /build/app .

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["./app"]
