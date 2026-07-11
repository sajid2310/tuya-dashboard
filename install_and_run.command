#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "=== Tuya Dashboard: installing dependencies ==="
PIP_BIN="pip3"
command -v pip3 >/dev/null 2>&1 || PIP_BIN="pip"
"$PIP_BIN" install -r requirements.txt
if [ $? -ne 0 ]; then
  echo ""
  echo "pip install failed - see the error above. You may need Python 3"
  echo "installed first (e.g. from python.org or 'brew install python3')."
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
