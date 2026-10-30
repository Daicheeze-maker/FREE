#!/usr/bin/env bash
# Production-style server on Linux. Binds to localhost by default; set BIND=0.0.0.0:8000 to expose on the network.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
export VELORA_ENV=${VELORA_ENV:-production}
flask --app wsgi init-db >/dev/null
exec gunicorn wsgi:app \
  --bind "${BIND:-127.0.0.1:8000}" \
  --workers "${WORKERS:-3}" \
  --timeout 30 \
  --access-logfile - \
  --error-logfile -
