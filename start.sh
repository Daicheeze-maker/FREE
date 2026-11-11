#!/usr/bin/env bash
# Velora Market: run `bash start.sh` to start the store.
# First run sets everything up automatically; after that it starts in seconds and opens your browser.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .venv/bin/activate ]; then
  echo "First run: setting things up. This takes a minute or two..."
  bash scripts/setup.sh
fi

. .venv/bin/activate
python -m flask --app wsgi init-db >/dev/null
python -m flask --app wsgi seed >/dev/null

export OPEN_BROWSER=${OPEN_BROWSER:-1}
echo "Velora Market is starting at http://127.0.0.1:${PORT:-5000}  (Ctrl+C to stop)"
exec python serve.py
