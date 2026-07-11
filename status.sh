#!/usr/bin/env bash
# Report whether the Tuya Dashboard is currently running.
set -euo pipefail
cd "$(dirname "$0")"

DATA_DIR="${DATA_DIR:-data}"
PIDFILE="$DATA_DIR/dashboard.pid"
PORT="${PORT:-8080}"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Running (PID $(cat "$PIDFILE")) at http://localhost:${PORT}"
else
  echo "Not running."
fi
