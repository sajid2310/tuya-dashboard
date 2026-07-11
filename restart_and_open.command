#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "=== Restarting Tuya Dashboard ==="
./stop.sh
sleep 1
./start.sh
sleep 1
open "http://localhost:8080"
echo ""
echo "Done - this window can be closed."
read -p "Press Enter to close this window..."
