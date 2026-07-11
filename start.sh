#!/usr/bin/env bash
# Start the Tuya Dashboard in the background (bare-Python route).
# Usage: ./start.sh   (respects PORT / DATA_DIR / APP_SECRET_KEY env vars if set)
set -euo pipefail
cd "$(dirname "$0")"

DATA_DIR="${DATA_DIR:-data}"
PIDFILE="$DATA_DIR/dashboard.pid"
LOGFILE="$DATA_DIR/dashboard.log"
PORT="${PORT:-8080}"
mkdir -p "$DATA_DIR"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Already running (PID $(cat "$PIDFILE")) at http://localhost:${PORT}"
  echo "Run ./stop.sh first if you want to restart it."
  exit 0
fi

PYTHON_BIN="python3"
if [ -x ".venv/bin/python3" ]; then
  PYTHON_BIN=".venv/bin/python3"
fi

if ! "$PYTHON_BIN" -c "import flask, tinytuya, cryptography, psutil" >/dev/null 2>&1; then
  echo "Dependencies look missing. Run ./install_and_run.command, or:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

export PORT DATA_DIR
nohup "$PYTHON_BIN" app.py >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
sleep 1

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Tuya Dashboard started (PID $(cat "$PIDFILE"))."
  echo "  URL:  http://localhost:${PORT}"
  echo "  Logs: tail -f $LOGFILE"
else
  echo "Failed to start - check $LOGFILE for details."
  rm -f "$PIDFILE"
  exit 1
fi
