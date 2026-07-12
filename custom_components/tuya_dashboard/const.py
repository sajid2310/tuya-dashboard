"""Constants for the Tuya Local Dashboard integration.

This integration is intentionally self-contained: it does not depend on
any other HACS integration (e.g. LocalTuya) or any other Lovelace card
(e.g. flex-table-card). Discovery, local control, and the dashboard UI
itself all ship in this one repository - the only third-party dependency
is the `tinytuya` library, which is the Tuya local-protocol implementation
itself, not a competing project.
"""

DOMAIN = "tuya_dashboard"

CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_REGION = "region"

DEFAULT_REGION = "us"
DEFAULT_SCAN_INTERVAL = 120  # seconds between background re-syncs
DEFAULT_SCANTIME = 12        # seconds spent listening for LAN broadcasts per sync

REGIONS = {
    "cn": "China",
    "us": "Western America",
    "us-e": "Eastern America",
    "eu": "Central Europe",
    "eu-w": "Western Europe",
    "in": "India",
    "sg": "Singapore",
}

# ---------------------------------------------------------------------------
# Device "type" classification and control layout - same convention as the
# standalone dashboard (app.py), kept in sync deliberately.
# ---------------------------------------------------------------------------
CATEGORY_TYPES = {
    "kg": "switch",
    "tgkg": "switch",
    "tdq": "switch",
    "cz": "plug",
    "pc": "plug",
    "insert_switch": "plug",
    "dj": "light",
    "dc": "light",
    "dd": "light",
    "xdd": "light",
    "fs": "fan",
    "fsd": "fan",
}

GANG_SWITCH_DPS = [str(n) for n in range(1, 7)]
FAN_SWITCH_DP = "1"
FAN_SPEED_DP = "3"

# ---------------------------------------------------------------------------
# MAC/ARP sweep tuning (same technique/limits as the standalone dashboard)
# ---------------------------------------------------------------------------
TUYA_LOCAL_PORT = 6668
MAX_SWEEP_HOSTS_PER_NET = 1024
MAX_NETWORKS_SWEPT = 4

# ---------------------------------------------------------------------------
# Bundled frontend panel
# ---------------------------------------------------------------------------
PANEL_URL_PATH = "tuya-dashboard"
PANEL_JS_FILENAME = "tuya-dashboard-panel.js"

SERVICE_LIST_DEVICES = "list_devices"
SERVICE_DIAGNOSE_DEVICE = "diagnose_device"
SERVICE_SET_CONTROL = "set_control"
