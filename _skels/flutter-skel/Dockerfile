# ---------------------------------------------------------------------------
# Multi-stage Dockerfile for Flutter web frontend
# ---------------------------------------------------------------------------

# -- Stage 1: Build --------------------------------------------------------
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        unzip \
        xz-utils \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Flutter SDK (stable channel)
ENV FLUTTER_HOME=/opt/flutter
ENV PATH="${FLUTTER_HOME}/bin:${FLUTTER_HOME}/bin/cache/dart-sdk/bin:${PATH}"

RUN git clone --depth 1 --branch stable https://github.com/flutter/flutter.git ${FLUTTER_HOME} && \
    flutter precache --web && \
    flutter config --no-analytics && \
    dart --disable-analytics

WORKDIR /build

COPY pubspec.yaml pubspec.lock* analysis_options.yaml ./
RUN flutter pub get

COPY lib/ ./lib/
COPY web/ ./web/
COPY assets/ ./assets/
COPY .env* ./

RUN flutter build web --release

# -- Stage 2: Production (nginx) ------------------------------------------
FROM nginx:alpine AS production

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/build/web /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1
