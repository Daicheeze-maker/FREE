#!/usr/bin/env bash
# One-time setup on Linux/macOS: virtualenv, dependencies, .env, database + demo data.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'

[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  key=$(python -c "import secrets; print(secrets.token_hex(32))")
  sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=${key}/" .env && rm -f .env.bak
  echo "Created .env with a fresh SECRET_KEY."
fi

flask --app wsgi init-db
flask --app wsgi seed
echo "Setup complete. Start with: scripts/run.sh   (or scripts/run_gunicorn.sh)"
