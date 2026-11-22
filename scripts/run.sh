#!/usr/bin/env bash
# Start Aurelune with Waitress. HOST=0.0.0.0 scripts/run.sh to allow access from other devices.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
# Install anything new in requirements.txt (quick when everything is already there)
python -m pip install -q --disable-pip-version-check --retries 1 --timeout 10 -r requirements.txt || true
python -m flask --app wsgi init-db >/dev/null
python -m flask --app wsgi seed   # loads demo products only if the catalog is empty
python -m flask --app wsgi upgrade-demo
python -m flask --app wsgi ensure-admin
exec python serve.py
