#!/usr/bin/env bash
# Stop the Tuya Dashboard started by ./start.sh
set -euo pipefail
cd "$(dirname "$0")"

DATA_DIR="${DATA_DIR:-data}"
PIDFILE="$DATA_DIR/dashboard.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "Not running (no $PIDFILE found)."
  exit 0
fi

PID="$(cat "$PIDFILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped Tuya Dashboard (PID $PID)."
else
  echo "PID $PID from $PIDFILE wasn't running (stale pidfile) - cleaning up."
fi
rm -f "$PIDFILE"
