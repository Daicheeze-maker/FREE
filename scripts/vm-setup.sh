#!/usr/bin/env bash
# One-command setup inside an Ubuntu virtual machine (22.04 / 24.04). Run from the store folder:
#
#     bash scripts/vm-setup.sh              # install everything + run the store as a service that starts at boot
#     bash scripts/vm-setup.sh --no-service # install everything; start it yourself with: bash start.sh
#
# What it does: installs Python and tools (apt), creates the isolated .venv with the pinned packages, writes .env with a
# fresh SECRET_KEY and HOST=0.0.0.0 (needed for VirtualBox port forwarding), creates the database, installs the
# 'aurelune' systemd service (auto-start, auto-restart), then runs scripts/vm-check.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"
PORT_DEFAULT=5000
SERVICE=1
[ "${1:-}" = "--no-service" ] && SERVICE=0

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "1/5 System packages"
if command -v apt-get >/dev/null 2>&1; then
  need=()
  for pkg in python3 python3-venv git curl; do  # pip comes inside the .venv; python3-pip would pull in compilers
    dpkg -s "$pkg" >/dev/null 2>&1 || need+=("$pkg")
  done
  if [ ${#need[@]} -gt 0 ]; then
    echo "Installing: ${need[*]} (your password may be asked)"
    sudo apt-get update -y
    sudo apt-get install -y --no-install-recommends "${need[@]}"
  else
    echo "Python, venv, git and curl are already installed."
  fi
else
  echo "Not an apt-based system: make sure python3 (3.11+), python3-venv and curl are installed."
fi
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is needed"'
echo "Python: $(python3 --version)"

say "2/5 Isolated environment (.venv), packages, .env and database"
bash scripts/setup.sh

say "3/5 Network settings in .env"
set_env() {  # set_env KEY VALUE: replace the line or add it
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}
set_env HOST 0.0.0.0
grep -q '^PORT=' .env || set_env PORT "$PORT_DEFAULT"
PORT="$(grep '^PORT=' .env | cut -d= -f2)"
echo "The store will listen on 0.0.0.0:${PORT} (all network interfaces), so VirtualBox port forwarding can reach it."

if [ "$SERVICE" = "1" ] && command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  say "4/5 Service that starts the store at boot and restarts it if it stops"
  case "$DIR" in *" "*) echo "The folder path has a space in it ($DIR). Move the store to a folder without spaces, e.g. ~/aurelune, and run this again."; exit 1;; esac
  sed -e "s|@USER@|$(id -un)|g" -e "s|@DIR@|${DIR}|g" deploy/aurelune.service | sudo tee /etc/systemd/system/aurelune.service >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable aurelune >/dev/null 2>&1
  sudo systemctl restart aurelune
  printf "Waiting for the store to answer"
  for _ in $(seq 1 40); do
    if curl -fsS -m 2 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then echo " ... up."; break; fi
    printf "."; sleep 1
  done
else
  say "4/5 Service skipped"
  echo "Start the store yourself with:  bash start.sh"
fi

say "5/5 Health check"
bash scripts/vm-check.sh || true

cat <<EOF

Done.
  In the VM's browser:     http://127.0.0.1:${PORT}
  From your own PC:        add a VirtualBox port-forwarding rule (Host Port ${PORT} -> Guest Port ${PORT}), then open http://127.0.0.1:${PORT}
  Check everything again:  bash scripts/vm-check.sh
EOF
if [ "$SERVICE" = "1" ] && command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  cat <<EOF
  Service commands:        sudo systemctl status aurelune | sudo systemctl restart aurelune | journalctl -u aurelune -f
EOF
fi
