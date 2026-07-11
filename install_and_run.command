#!/usr/bin/env bash
cd "$(dirname "$0")"

PYTHON_BIN="python3"
command -v python3 >/dev/null 2>&1 || PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 wasn't found. Install it first (e.g. from python.org or"
  echo "'brew install python3'), then re-run this."
  read -p "Press Enter to close this window..."
  exit 1
fi

echo "=== Tuya Dashboard: setting up a virtual environment (.venv) ==="
# A venv avoids fighting your system Python's package manager (macOS/Homebrew
# Python blocks plain 'pip install' outside a venv on purpose - this is the
# correct fix, not something to override).
if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

echo "=== Installing dependencies ==="
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt
if [ $? -ne 0 ]; then
  echo ""
  echo "pip install failed - see the error above."
  read -p "Press Enter to close this window..."
  exit 1
fi

echo ""
echo "=== Starting Tuya Dashboard ==="
chmod +x start.sh stop.sh restart.sh status.sh
./start.sh
sleep 1
open "http://localhost:8080"

echo ""
echo "Done. This window can be closed - the app keeps running in the background."
echo "From the tuya-dashboard folder: ./status.sh to check it, ./stop.sh to stop it."
read -p "Press Enter to close this window..."
