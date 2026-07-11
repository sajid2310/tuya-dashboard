#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "=== Freeing port 8080 (killing any stale/orphaned process) ==="
PIDS=$(lsof -ti:8080 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "Killing stale process(es): $PIDS"
  kill -9 $PIDS 2>/dev/null || true
  sleep 1
else
  echo "Nothing was holding port 8080."
fi
rm -f data/dashboard.pid

echo ""
echo "=== Setting up virtual environment (.venv) ==="
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

echo "=== Installing dependencies ==="
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt

echo ""
echo "=== Starting Tuya Dashboard ==="
chmod +x start.sh stop.sh restart.sh status.sh
./start.sh
sleep 1
open "http://localhost:8080"

echo ""
echo "Done - this window can be closed."
read -p "Press Enter to close this window..."
