#!/usr/bin/env bash
# Start Velora with Waitress. HOST=0.0.0.0 scripts/run.sh to allow access from other devices.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
python -m flask --app wsgi init-db >/dev/null
python -m flask --app wsgi seed   # loads demo products only if the catalog is empty
exec python serve.py
