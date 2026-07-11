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

if [ ! -d ".venv" ] && ! python3 -c "import flask, tinytuya, cryptography, psutil" >/dev/null 2>&1; then
  echo "Dependencies look missing - run: pip install -r requirements.txt"
  exit 1
fi

export PORT DATA_DIR
nohup python3 app.py >> "$LOGFILE" 2>&1 &
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
