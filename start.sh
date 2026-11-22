#!/usr/bin/env bash
# Aurelune: run `bash start.sh` to start the store.
# First run sets everything up automatically; after that it starts in seconds and opens your browser.
set -euo pipefail
cd "$(dirname "$0")"

# Step 1: get the latest version from GitHub, then run this script again from the top (bash reads it while running)
if [ "${1:-}" != "--updated" ]; then
  if command -v git >/dev/null 2>&1 && [ -d .git ]; then
    echo "Checking for updates..."
    git pull --ff-only origin claude/eloquent-archimedes-lakibj || echo "Could not update automatically. Starting the version you have."
  fi
  exec bash "$0" --updated
fi
git log -1 --format='Store version: %h (%cd)' --date=short 2>/dev/null || true


if [ ! -f .venv/bin/activate ]; then
  echo "First run: setting things up. This takes a minute or two..."
  bash scripts/setup.sh
fi

. .venv/bin/activate
python -m pip install -q --disable-pip-version-check --retries 1 --timeout 10 -r requirements.txt || true
python -m flask --app wsgi init-db >/dev/null
python -m flask --app wsgi seed >/dev/null
python -m flask --app wsgi upgrade-demo
python -m flask --app wsgi fill-photos

export OPEN_BROWSER=${OPEN_BROWSER:-1}
echo "Aurelune is starting at http://127.0.0.1:${PORT:-5000}  (Ctrl+C to stop)"
exec python serve.py
