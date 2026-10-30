#!/usr/bin/env bash
# Start Velora with Waitress. HOST=0.0.0.0 scripts/run.sh to allow access from other devices.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
flask --app wsgi init-db >/dev/null
flask --app wsgi seed   # loads demo products only if the catalog is empty
exec python serve.py
