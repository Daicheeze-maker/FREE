#!/usr/bin/env bash
# Development setup on Linux / macOS (Windows: use scripts/setup-windows.ps1).
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "Install FFmpeg first (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
backend/.venv/bin/pip uninstall -y opencv-python >/dev/null 2>&1 || true
(cd frontend && npm ci && npm run build)
echo "Run:  cd backend && .venv/bin/python -m clipforge.main   then open http://127.0.0.1:8756"
