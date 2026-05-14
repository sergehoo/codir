#!/usr/bin/env sh
# CODIR — entrypoint conteneur API.
# Usage : ./docker-entrypoint.sh [dev|prod|migrate|shell]
set -e

MODE="${1:-prod}"
echo "[entrypoint] mode=$MODE"

# ─── Wait for DB (max 60s) ─────────────────────────────────────
echo "[entrypoint] Waiting for Postgres at ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}..."
COUNT=0
until python -c "import psycopg2, os; psycopg2.connect(host=os.getenv('POSTGRES_HOST','postgres'), port=os.getenv('POSTGRES_PORT','5432'), user=os.getenv('POSTGRES_USER','codir'), password=os.getenv('POSTGRES_PASSWORD','codir'), dbname=os.getenv('POSTGRES_DB','codir')).close()" 2>/dev/null
do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -gt 30 ]; then
    echo "[entrypoint] FATAL: Postgres unreachable after 60s" >&2
    exit 1
  fi
  sleep 2
done
echo "[entrypoint] Postgres ready."

# ─── Always migrate (idempotent) ───────────────────────────────
echo "[entrypoint] Running migrations..."
python manage.py migrate --no-input

# ─── Collectstatic en prod ─────────────────────────────────────
if [ "$MODE" = "prod" ]; then
  echo "[entrypoint] Collecting static files..."
  python manage.py collectstatic --no-input --clear || true
fi

# ─── Dispatch ──────────────────────────────────────────────────
case "$MODE" in
  dev)
    echo "[entrypoint] Starting Django runserver on 0.0.0.0:8000"
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  prod)
    echo "[entrypoint] Starting Gunicorn"
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-4}" \
      --worker-class gthread \
      --threads "${GUNICORN_THREADS:-8}" \
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
  *)
    echo "[entrypoint] Unknown mode '$MODE'" >&2
    exit 1
    ;;
esac
