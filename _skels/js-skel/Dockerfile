# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for Node.js service
# ---------------------------------------------------------------------------

# -- Stage 1: Build --------------------------------------------------------
FROM node:22-bookworm-slim AS builder

WORKDIR /build

# Cache dependencies first
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# -- Stage 2: Production ---------------------------------------------------
FROM node:22-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/node_modules ./node_modules
COPY package.json ./
COPY src/ ./src/
COPY eslint.config.js ./

RUN chown -R node:node /app

USER node

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["node", "src/app.js"]
