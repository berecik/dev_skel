# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for React + Vite frontend
# ---------------------------------------------------------------------------

# -- Stage 1: Build --------------------------------------------------------
FROM node:22-bookworm-slim AS builder

WORKDIR /build

# Cache dependencies first
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY index.html tsconfig.json vite.config.ts eslint.config.js ./
COPY src/ ./src/
RUN npm run build

# -- Stage 2: Production (nginx) ------------------------------------------
FROM nginx:alpine AS production

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

# -- Stage 3: Development (vite dev server) --------------------------------
FROM node:22-bookworm-slim AS development

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

ENTRYPOINT ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
