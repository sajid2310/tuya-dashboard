#!/usr/bin/env bash
# Restart the Tuya Dashboard.
set -euo pipefail
cd "$(dirname "$0")"
./stop.sh
sleep 1
./start.sh
