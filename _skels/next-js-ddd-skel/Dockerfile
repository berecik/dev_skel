# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for Next.js API backend
# ---------------------------------------------------------------------------

# -- Stage 1: Dependencies -------------------------------------------------
FROM node:22-bookworm-slim AS deps

WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci

# -- Stage 2: Build --------------------------------------------------------
FROM node:22-bookworm-slim AS builder

WORKDIR /build

COPY --from=deps /build/node_modules ./node_modules
COPY . .

RUN npm run build

# -- Stage 3: Production ---------------------------------------------------
FROM node:22-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/.next/standalone ./
COPY --from=builder /build/.next/static ./.next/static

RUN mkdir -p /app/data && chown -R node:node /app

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:3000/api/health || exit 1

ENTRYPOINT ["node", "server.js"]
