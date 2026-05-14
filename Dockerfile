### Multi-stage Dockerfile pour Django backend CODIR
### Cible : image runtime mince, sans toolchain, exécution non-root.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        tini \
        curl \
        ca-certificates \
        tesseract-ocr \
        tesseract-ocr-fra \
        libsndfile1 \
        ffmpeg \
        fonts-liberation \
        && rm -rf /var/lib/apt/lists/*

# ── Builder ─────────────────────────────────────────────────────
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        pkg-config \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN python -m pip install --prefix=/install --upgrade pip && \
    python -m pip install --prefix=/install -r requirements.txt

# ── Runtime ─────────────────────────────────────────────────────
FROM base AS runtime
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=app:app . .

USER app

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PORT=8000

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "8", \
     "--max-requests", "10000", \
     "--max-requests-jitter", "500", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
