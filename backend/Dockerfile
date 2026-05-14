### Multi-stage Dockerfile — Django backend CODIR
### Image runtime mince, exécution non-root, entrypoint signalé via tini.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Africa/Abidjan

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
        tzdata \
        && rm -rf /var/lib/apt/lists/*

# ── Builder ─────────────────────────────────────────────
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        pkg-config \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
# Upgrade pip dans le site-packages global du builder (pas dans /install),
# puis utiliser ce pip pour installer les deps vers /install
RUN python -m pip install --upgrade pip && \
    python -m pip install --prefix=/install -r requirements.txt

# ── Runtime ─────────────────────────────────────────────
FROM base AS runtime
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Bibliothèques Python compilées
COPY --from=builder /install /usr/local

WORKDIR /app

# Copie du code applicatif
COPY --chown=app:app . .

# Garantit que l'entrypoint est exécutable
RUN test -f /app/scripts/docker-entrypoint.sh && \
    chmod +x /app/scripts/docker-entrypoint.sh || true

# Répertoires runtime créés avec les bons droits
RUN mkdir -p /app/staticfiles /app/logs /var/www/media && \
    chown -R app:app /app/staticfiles /app/logs /var/www/media

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
