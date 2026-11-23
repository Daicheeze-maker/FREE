#!/usr/bin/env bash
# Health check for the store inside the VM. Run from the store folder:   bash scripts/vm-check.sh
# Shows the VM's resources, checks the isolated environment and packages, runs the app's own checks (flask doctor),
# checks the service, the port and the main pages over HTTP, and looks for errors in the recent log.
set -uo pipefail
cd "$(dirname "$0")/.."
FAILED=0
PORT="$( (grep -s '^PORT=' .env || echo PORT=5000) | tail -1 | cut -d= -f2)"
PORT="${PORT:-5000}"
ok()   { printf '  [ OK ] %s\n' "$*"; }
warn() { printf '  [WARN] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; FAILED=$((FAILED + 1)); }
head_() { printf '\n%s\n' "$*"; }

head_ "VM resources"
if [ -r /etc/os-release ]; then . /etc/os-release; ok "System: ${PRETTY_NAME:-unknown}"; fi
CPUS="$(nproc 2>/dev/null || echo 1)"
RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)"
DISK_GB="$(df -Pk . | awk 'NR==2 {print int($4/1024/1024)}')"
[ "$CPUS" -ge 2 ] && ok "CPUs: $CPUS" || warn "CPUs: $CPUS (2 or more recommended)"
[ "$RAM_MB" -ge 2000 ] && ok "Memory: ${RAM_MB} MB" || warn "Memory: ${RAM_MB} MB (2048 MB or more recommended)"
[ "$DISK_GB" -ge 3 ] && ok "Free disk: ${DISK_GB} GB" || warn "Free disk: ${DISK_GB} GB (keep at least 3 GB free)"

head_ "Isolated environment"
if [ -x .venv/bin/python ]; then
  ok ".venv exists ($(.venv/bin/python --version 2>&1))"
  if .venv/bin/python -m pip check >/tmp/aurelune-pip-check.txt 2>&1; then
    ok "No package conflicts (pip check)"
  else
    bad "Package conflicts: $(head -3 /tmp/aurelune-pip-check.txt | tr '\n' ' ')"
  fi
else
  bad ".venv is missing: run bash scripts/vm-setup.sh (or bash scripts/setup.sh)"
fi

head_ "Store checks (flask doctor)"
if [ -x .venv/bin/python ]; then
  if .venv/bin/python -m flask --app wsgi doctor 2>/dev/null | sed 's/^/  /'; then :; else bad "flask doctor found problems (see above)"; fi
fi

head_ "Service and network"
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files aurelune.service >/dev/null 2>&1 \
   && systemctl list-unit-files aurelune.service | grep -q aurelune; then
  STATE="$(systemctl is-active aurelune 2>/dev/null)"
  ENABLED="$(systemctl is-enabled aurelune 2>/dev/null)"
  RESTARTS="$(systemctl show -p NRestarts --value aurelune 2>/dev/null || echo ?)"
  [ "$STATE" = "active" ] && ok "Service 'aurelune' is running (starts at boot: $ENABLED, automatic restarts so far: $RESTARTS)" \
                          || bad "Service 'aurelune' is $STATE: sudo systemctl restart aurelune, then journalctl -u aurelune -n 50"
else
  warn "No 'aurelune' service installed (fine if you start the store with bash start.sh)"
fi
if command -v ss >/dev/null 2>&1; then
  LISTEN="$(ss -ltnH 2>/dev/null | awk '{print $4}' | grep -E "[:.]${PORT}\$" | head -1)"
else  # no ss: read the kernel's table of listening sockets (state 0A) directly
  HEXPORT="$(printf '%04X' "$PORT")"
  LISTEN="$(awk -v p="$HEXPORT" 'NR > 1 && $4 == "0A" { split($2, a, ":"); if (a[2] == p) { print a[1]; exit } }' /proc/net/tcp 2>/dev/null)"
  case "$LISTEN" in 00000000) LISTEN="0.0.0.0:${PORT}";; 0100007F) LISTEN="127.0.0.1:${PORT}";; "") ;; *) LISTEN="(address ${LISTEN}):${PORT}";; esac
fi
if [ -n "$LISTEN" ]; then
  case "$LISTEN" in
    0.0.0.0:*|\*:*|\[::\]:*) ok "Listening on $LISTEN (reachable through VirtualBox port forwarding)";;
    *) warn "Listening on $LISTEN only: set HOST=0.0.0.0 in .env so port forwarding from your PC works";;
  esac
elif systemctl list-unit-files aurelune.service 2>/dev/null | grep -q aurelune; then
  bad "Nothing is listening on port $PORT: sudo systemctl restart aurelune, then journalctl -u aurelune -n 50"
else
  warn "The store isn't running yet: start it with  bash start.sh"
fi

head_ "Pages over HTTP (http://127.0.0.1:${PORT})"
if [ -n "$LISTEN" ] && command -v curl >/dev/null 2>&1; then
  for path in /healthz / /shop/ /shop/c/dress-watches /account/login /api/v1 /api/v1/health "/api/v1/products?per_page=1" /api/docs; do
    start=$(date +%s%N)
    code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "http://127.0.0.1:${PORT}${path}")"
    ms=$(( ($(date +%s%N) - start) / 1000000 ))
    [ "$code" = "200" ] && ok "$path -> 200 (${ms} ms)" || bad "$path -> $code"
  done
else
  warn "Skipped (store not running or curl missing)"
fi

head_ "Recent log (last 30 minutes)"
if command -v journalctl >/dev/null 2>&1 && systemctl list-unit-files aurelune.service 2>/dev/null | grep -q aurelune; then
  ERRORS="$(journalctl -u aurelune --since '-30min' --no-pager 2>/dev/null | grep -ciE 'traceback|exception|error [0-9]{3}| 500 ' || true)"
  [ "${ERRORS:-0}" = "0" ] && ok "No errors or tracebacks in the service log" \
                           || bad "$ERRORS error line(s) in the log: journalctl -u aurelune --since '-30min'"
else
  warn "No service log to read (started by hand: errors show in that terminal)"
fi

echo
if [ "$FAILED" = "0" ]; then echo "VM CHECK: everything is OK."; else echo "VM CHECK: $FAILED problem(s) found (see [FAIL] lines)."; fi
exit $(( FAILED > 0 ))
