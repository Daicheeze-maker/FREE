#!/usr/bin/env bash
# Start Velora with Waitress. HOST=0.0.0.0 scripts/run.sh to allow access from other devices.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
flask --app wsgi init-db >/dev/null
exec python serve.py
