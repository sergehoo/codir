#!/usr/bin/env sh
# CODIR — entrypoint conteneur API
# Usage : docker-entrypoint.sh [dev|prod|migrate|shell|worker|beat]
set -e

MODE="${1:-prod}"
echo "[entrypoint] mode=$MODE"

# ─── HF cache dir : best-effort writable check ────────────────
# Le volume Docker `codir_hfcache` peut être créé avec ownership root.
# Si on tourne en user non-root (app), on tente un chown si on a les droits,
# sinon on log un warning utile.
HF_DIR="${HF_HOME:-/var/cache/codir/hf}"
if [ -n "$HF_DIR" ] && [ -d "$HF_DIR" ]; then
  if ! [ -w "$HF_DIR" ]; then
    echo "[entrypoint] WARN: HF cache $HF_DIR non-writable (uid=$(id -u))."
    echo "[entrypoint]      Fix one-shot:"
    echo "[entrypoint]      docker compose exec --user root <svc> chown -R app:app $HF_DIR"
  else
    echo "[entrypoint] HF cache $HF_DIR writable: OK"
  fi
fi

# ─── Wait for DB (max 60s) ─────────────────────────────────────
DB_HOST="${POSTGRES_HOST:-codirDB}"
DB_PORT="${POSTGRES_PORT:-5432}"
echo "[entrypoint] Waiting for Postgres at ${DB_HOST}:${DB_PORT}..."

COUNT=0
until python -c "
import os, psycopg2
psycopg2.connect(
    host=os.getenv('POSTGRES_HOST','codirDB'),
    port=os.getenv('POSTGRES_PORT','5432'),
    user=os.getenv('POSTGRES_USER','codir'),
    password=os.getenv('POSTGRES_PASSWORD','codir'),
    dbname=os.getenv('POSTGRES_DB','codir'),
).close()
" 2>/dev/null
do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -gt 30 ]; then
    echo "[entrypoint] FATAL: Postgres unreachable after 60s" >&2
    exit 1
  fi
  sleep 2
done
echo "[entrypoint] Postgres ready."

# ─── Migrate (idempotent) — sauf en mode worker/beat ──────────
case "$MODE" in
  worker|beat)
    echo "[entrypoint] Skipping migrations for $MODE"
    ;;
  *)
    echo "[entrypoint] Running migrations..."
    python manage.py migrate --no-input
    ;;
esac

# ─── Collectstatic en prod ─────────────────────────────────────
if [ "$MODE" = "prod" ]; then
  echo "[entrypoint] Collecting static files..."
  if ! python manage.py collectstatic --no-input --clear; then
    echo "[entrypoint] WARNING: collectstatic failed — admin CSS may not load" >&2
  fi
fi

# ─── Dispatch ──────────────────────────────────────────────────
case "$MODE" in
  dev)
    echo "[entrypoint] Starting Django runserver on 0.0.0.0:8000"
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  prod)
    echo "[entrypoint] Starting Gunicorn"
    # --timeout 600 : autorise les uploads d'enregistrements jusqu'à ~600 Mo
    # sans que le worker soit killé. Sans cette option, la valeur par défaut
    # (30s) tue toute requête longue → uploads avortés à mi-chemin.
    # --limit-request-line 8190 (default) reste suffisant, ce sont des POST.
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-4}" \
      --worker-class gthread \
      --threads "${GUNICORN_THREADS:-8}" \
      --timeout "${GUNICORN_TIMEOUT:-600}" \
      --max-requests 10000 \
      --max-requests-jitter 500 \
      --graceful-timeout 30 \
      --access-logfile - \
      --error-logfile -
    ;;
  migrate)
    echo "[entrypoint] Migrations done — exiting."
    exit 0
    ;;
  shell)
    exec python manage.py shell
    ;;
  worker)
    exec celery -A config worker -l info -Q "${CELERY_QUEUES:-default,celery,notifications}"
    ;;
  beat)
    exec celery -A config beat -l info -S django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    echo "[entrypoint] Unknown mode '$MODE' — running command as-is"
    exec "$@"
    ;;
esac
