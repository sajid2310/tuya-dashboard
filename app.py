"""
Tuya Local Device Dashboard
============================
A single-page web dashboard (TasmoAdmin-style) for discovering and
controlling Tuya smart switches on your local network, built on top of
the `tinytuya` library.

Discovery works two ways, and you can use either or both:

  1. Local network scan  - listens for the UDP broadcast packets Tuya
     devices send out on the LAN (ports 6666/6667/7000). This finds the
     device ID, IP and protocol version, but Tuya devices only reveal a
     usable local_key once they've been paired through the Tuya app /
     cloud, so this alone is not enough to control them.

  2. Tuya Cloud API       - using your Tuya IoT Platform "Access ID /
     Client ID" and "Access Secret / Client Secret", queries the official
     Cloud API for the full list of devices linked to your account,
     including their names, categories and local_keys.

A "Sync" click runs both and matches them up by device ID, giving you
IP + local_key + version for every switch in one table -- exactly what
you need to plug into Home Assistant's "Tuya Local" integration, and
enough to turn devices on/off directly from this page too.

Run this ON the same LAN as your Tuya devices (UDP broadcast doesn't
cross subnets/VLANs or the public internet).

There's a third discovery path too: if the Cloud API told us a device's
MAC address but the UDP broadcast scan didn't catch it (broadcasts are
easy to miss - not every device sends one every scan window), we sweep
the local subnet(s) on Tuya's local port (6668) and cross-reference the
machine's ARP table for that MAC, which resolves it straight to an IP -
the same trick a DHCP-lease/ARP lookup would give you, but without
needing access to your router.
"""
import concurrent.futures
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
import traceback
from pathlib import Path

from flask import Flask, jsonify, request, render_template
from cryptography.fernet import Fernet, InvalidToken

import tinytuya
from tinytuya import scanner

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"
DEVICES_FILE = DATA_DIR / "devices.json"
SECRET_KEY_FILE = DATA_DIR / "secret.key"

_store_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Encryption at rest for credentials (Tuya access_secret + device local_keys).
#
# The encryption key comes from the APP_SECRET_KEY env var if set (this is
# what you should do in any production/shared deployment - inject it from a
# secrets manager, and back it up, since losing it makes all stored
# credentials unrecoverable and everyone will need to re-sync).
#
# If APP_SECRET_KEY isn't set (e.g. a quick local run), a key is generated
# and persisted to data/secret.key on first run so restarts keep working.
# That file is exactly as sensitive as the secrets it protects - it's
# gitignored, and must never be committed or shipped in a Docker image.
# ---------------------------------------------------------------------------
_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.environ.get("APP_SECRET_KEY", "").strip()
    if key:
        key = key.encode()
    elif SECRET_KEY_FILE.exists():
        key = SECRET_KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        SECRET_KEY_FILE.write_bytes(key)
        try:
            os.chmod(SECRET_KEY_FILE, 0o600)
        except OSError:
            pass
        print("[tuya-dashboard] Generated a new local encryption key at %s. "
              "In production, set APP_SECRET_KEY instead so the key survives "
              "redeploys and isn't sitting next to the data it protects." % SECRET_KEY_FILE)
    _fernet = Fernet(key)
    return _fernet


def encrypt_secret(plaintext):
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token):
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        # Key rotated/lost, or legacy plaintext value from before encryption
        # was added - treat as plaintext so nothing hard-crashes, but this
        # means the value is effectively unusable/insecure until re-entered.
        return token if len(token) < 64 and " " not in token else ""


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_config():
    cfg = load_json(CONFIG_FILE, {"access_id": "", "access_secret": "", "region": "us"})
    cfg["access_secret"] = decrypt_secret(cfg.get("access_secret", ""))
    return cfg


def save_config(cfg):
    to_write = dict(cfg)
    to_write["access_secret"] = encrypt_secret(cfg.get("access_secret", ""))
    with _store_lock:
        save_json(CONFIG_FILE, to_write)


def load_devices():
    raw = load_json(DEVICES_FILE, {})
    out = {}
    for dev_id, entry in raw.items():
        e = dict(entry)
        if e.get("key"):
            e["key"] = decrypt_secret(e["key"])
        out[dev_id] = e
    return out


def save_devices(devices):
    to_write = {}
    for dev_id, entry in devices.items():
        e = dict(entry)
        if e.get("key"):
            e["key"] = encrypt_secret(e["key"])
        to_write[dev_id] = e
    with _store_lock:
        save_json(DEVICES_FILE, to_write)


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
# MAC / ARP resolution ("DHCP-lease-lookup equivalent")
#
# Real DNS (nslookup) has nothing to resolve here - IoT devices don't have
# hostnames - and reading your router's actual DHCP lease table isn't
# something we can do generically (every router vendor exposes that
# differently, if at all). The universal LAN-layer equivalent is ARP: it's
# the table your OS already keeps mapping "IP <-> MAC" for anything it has
# recently talked to. So:
#
#   1. We enumerate this machine's local IPv4 subnet(s).
#   2. We attempt a plain TCP connect to port 6668 (Tuya's local protocol
#      port) against every host in those subnet(s). This is unprivileged -
#      no raw sockets/root needed - and as a side effect it forces the OS
#      to ARP-resolve every host that's actually online, whether or not
#      it answers on 6668.
#   3. We read back the OS ARP table and look up the MAC address(es) the
#      Cloud API told us about. A hit gives us that device's current IP.
#
# This only sees devices on the same L2 subnet as this machine (same
# constraint as the UDP broadcast scan / any local discovery approach).
# ---------------------------------------------------------------------------
TUYA_LOCAL_PORT = 6668
MAX_SWEEP_HOSTS_PER_NET = 1024   # skip absurdly large/misconfigured subnets
MAX_NETWORKS_SWEPT = 4           # cap total interfaces swept per sync

_ARP_LINE_RE = re.compile(
    r"\(?(\d{1,3}(?:\.\d{1,3}){3})\)?\s+at\s+([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})"
)


def _normalize_mac(mac):
    hexonly = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(hexonly) != 12:
        return ""
    return ":".join(hexonly[i:i + 2] for i in range(0, 12, 2)).lower()


def _local_ipv4_networks():
    """This machine's private IPv4 subnets, e.g. [IPv4Network('192.168.1.0/24')]."""
    nets = []
    if psutil is None:
        return nets
    try:
        all_addrs = psutil.net_if_addrs()
    except Exception:  # noqa: BLE001
        return nets
    for _iface, addrs in all_addrs.items():
        for a in addrs:
            if a.family != socket.AF_INET or not a.address or not a.netmask:
                continue
            try:
                net = ipaddress.ip_network(f"{a.address}/{a.netmask}", strict=False)
            except ValueError:
                continue
            if net.is_loopback or net.is_link_local or not net.is_private:
                continue
            if net.num_addresses > MAX_SWEEP_HOSTS_PER_NET:
                continue
            nets.append(net)
    seen = set()
    uniq = []
    for n in nets:
        if str(n) not in seen:
            seen.add(str(n))
            uniq.append(n)
    return uniq[:MAX_NETWORKS_SWEPT]


def _tcp_probe(ip, port=TUYA_LOCAL_PORT, timeout=0.35):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((str(ip), port)) == 0
    except OSError:
        return False


def _sweep_networks(networks, max_workers=128):
    """Attempt a TCP connect to every host in `networks`. Returns IPs that had
    port 6668 open (probable Tuya devices) - the sweep itself is what
    populates the OS ARP cache as a side effect for _read_arp_table()."""
    hosts = []
    for net in networks:
        hosts.extend(net.hosts())
    if not hosts:
        return []
    responsive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_tcp_probe, h): h for h in hosts}
        for fut in concurrent.futures.as_completed(futures):
            try:
                if fut.result():
                    responsive.append(str(futures[fut]))
            except Exception:  # noqa: BLE001
                pass
    return responsive


def _read_arp_table():
    """Return {ip: normalized_mac} from the OS ARP cache. Prefers
    /proc/net/arp (Linux, no external binary needed - works in the slim
    Docker image), falls back to parsing `arp -a` (macOS and Linux with
    net-tools installed)."""
    table = {}
    proc_arp = Path("/proc/net/arp")
    if proc_arp.exists():
        try:
            for line in proc_arp.read_text().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    ip, flags, mac = parts[0], parts[2], parts[3]
                    if flags != "0x0" and mac and mac != "00:00:00:00:00:00":
                        table[ip] = _normalize_mac(mac)
        except Exception:  # noqa: BLE001
            pass
        if table:
            return table
    try:
        out = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=5
        ).stdout
        for line in out.splitlines():
            m = _ARP_LINE_RE.search(line)
            if m:
                table[m.group(1)] = _normalize_mac(m.group(2))
    except Exception:  # noqa: BLE001
        pass
    return table


def _find_ips_by_mac(target_macs):
    """Sweep local subnets + read ARP table; return {normalized_mac: ip}
    for whichever of target_macs were found online."""
    wanted = {_normalize_mac(m) for m in target_macs if m}
    wanted.discard("")
    if not wanted:
        return {}
    networks = _local_ipv4_networks()
    if not networks:
        return {}
    _sweep_networks(networks)
    arp = _read_arp_table()
    return {mac: ip for ip, mac in arp.items() if mac in wanted}


# ---------------------------------------------------------------------------
# Background scan job
# ---------------------------------------------------------------------------
SCAN_JOB = {
    "running": False,
    "progress": "idle",
    "error": None,
    "cloud_error": None,
    "result": None,
    "started_at": None,
    "finished_at": None,
}
_job_lock = threading.Lock()


def _set_job(**kwargs):
    with _job_lock:
        SCAN_JOB.update(kwargs)


def _merge_and_store(scanned_by_id, cloud_list, mac_ip_map=None):
    """Merge local-scan results, Tuya Cloud device list, and (if used) the
    MAC/ARP sweep results into our store."""
    store = load_devices()
    now = time.time()
    mac_ip_map = mac_ip_map or {}

    # 1. Start from cloud list: authoritative for name / local_key / category.
    for dev in cloud_list:
        dev_id = dev.get("id")
        if not dev_id:
            continue
        entry = store.get(dev_id, {})
        entry.update({
            "id": dev_id,
            "name": dev.get("name") or entry.get("name") or dev_id,
            "key": dev.get("key") or entry.get("key", ""),
            "mac": dev.get("mac") or entry.get("mac", ""),
            "category": dev.get("category", entry.get("category", "")),
            "product_name": dev.get("product_name", entry.get("product_name", "")),
            "product_id": dev.get("product_id", entry.get("product_id", "")),
            "source": "cloud",
        })
        if dev.get("version"):
            entry["version"] = dev.get("version")
        store[dev_id] = entry

    # 2. Overlay local scan results: authoritative for IP / version / online.
    for dev_id, info in (scanned_by_id or {}).items():
        entry = store.get(dev_id, {})
        entry.update({
            "id": dev_id,
            "ip": info.get("ip", entry.get("ip", "")),
            "version": info.get("version") or entry.get("version", "3.3"),
            "mac": info.get("mac") or entry.get("mac", ""),
            "product_key": info.get("productKey", entry.get("product_key", "")),
            "online": True,
            "last_seen": now,
            "origin": info.get("origin", "broadcast"),
        })
        if not entry.get("name"):
            entry["name"] = info.get("name") or dev_id
        if not entry.get("key"):
            entry["key"] = info.get("key", "")
        store[dev_id] = entry

    # 3. Fill in IPs found via the MAC/ARP sweep, for devices the broadcast
    #    scan missed this round (we only get here for devices with a known
    #    MAC from the Cloud API that weren't already matched in step 2).
    matched_by_sweep = set()
    if mac_ip_map:
        for dev_id, entry in store.items():
            if dev_id in (scanned_by_id or {}):
                continue  # already have a fresher IP from the broadcast scan
            mac = _normalize_mac(entry.get("mac", ""))
            if mac and mac in mac_ip_map:
                entry["ip"] = mac_ip_map[mac]
                entry["online"] = True
                entry["last_seen"] = now
                entry["origin"] = "mac_sweep"
                store[dev_id] = entry
                matched_by_sweep.add(dev_id)

    # 4. Anything not seen this round at all -> mark offline.
    seen_ids = set((scanned_by_id or {}).keys()) | matched_by_sweep
    for dev_id, entry in store.items():
        if dev_id not in seen_ids:
            entry["online"] = False

    save_devices(store)
    return store, matched_by_sweep


def _run_scan(scantime, use_cloud, forcescan):
    try:
        _set_job(running=True, progress="Starting scan...", error=None,
                  cloud_error=None, result=None, started_at=time.time(), finished_at=None)

        cloud_list = []
        if use_cloud:
            cfg = load_config()
            if cfg.get("access_id") and cfg.get("access_secret"):
                _set_job(progress="Querying Tuya Cloud API for your device list...")
                try:
                    cloud = tinytuya.Cloud(
                        apiRegion=cfg.get("region", "us"),
                        apiKey=cfg["access_id"],
                        apiSecret=cfg["access_secret"],
                    )
                    raw = cloud.getdevices()
                    if isinstance(raw, dict) and raw.get("Error"):
                        _set_job(cloud_error=raw.get("Error"))
                    elif isinstance(raw, list):
                        cloud_list = raw
                    else:
                        _set_job(cloud_error="Unexpected response from Tuya Cloud API: %r" % (raw,))
                except Exception as e:  # noqa: BLE001
                    _set_job(cloud_error="Cloud API request failed: %s" % e)
            else:
                _set_job(cloud_error="No Access ID/Secret configured - skipping cloud lookup.")

        _set_job(progress="Listening on LAN for %ss (matching against %d cloud device%s)..." % (
            scantime, len(cloud_list), "" if len(cloud_list) == 1 else "s"))

        found = scanner.devices(
            byID=True,
            tuyadevices=cloud_list,
            scantime=scantime,
            color=False,
            poll=False,
            forcescan=bool(forcescan and cloud_list),
            verbose=False,
            # This runs headless (no terminal attached), so tinytuya must
            # never fall back to input() to ask "scan this network?" /
            # "poll local devices?" - that raises EOFError with no stdin.
            assume_yes=True,
        )

        # MAC/ARP sweep: for any cloud-known device with a MAC address that
        # the broadcast scan didn't catch this round, try to resolve its
        # current IP by sweeping the local subnet(s) and reading the ARP
        # table (see the big comment above _find_ips_by_mac).
        mac_ip_map = {}
        sweep_targets = []
        if cloud_list:
            found_ids = set((found or {}).keys())
            for dev in cloud_list:
                if dev.get("id") not in found_ids and dev.get("mac"):
                    sweep_targets.append(dev["mac"])
        if sweep_targets:
            _set_job(progress="Sweeping local subnet(s) for %d device(s) by MAC address..." % len(sweep_targets))
            try:
                mac_ip_map = _find_ips_by_mac(sweep_targets)
            except Exception as e:  # noqa: BLE001
                _set_job(cloud_error=(SCAN_JOB.get("cloud_error") or "") +
                          " MAC sweep failed: %s" % e)

        _set_job(progress="Merging results...")
        merged, matched_by_sweep = _merge_and_store(found, cloud_list, mac_ip_map)

        _set_job(
            running=False,
            progress="Done",
            result={
                "found_on_lan": len(found or {}),
                "found_by_mac_sweep": len(matched_by_sweep),
                "from_cloud": len(cloud_list),
                "total_known": len(merged),
            },
            finished_at=time.time(),
        )
    except Exception as e:  # noqa: BLE001
        _set_job(
            running=False,
            progress="Error",
            error="%s: %s" % (type(e).__name__, e),
            finished_at=time.time(),
        )
        traceback.print_exc()


@app.route("/api/scan", methods=["POST"])
def api_scan_start():
    with _job_lock:
        if SCAN_JOB["running"]:
            return jsonify({"error": "A scan is already running."}), 409
    body = request.get_json(silent=True) or {}
    scantime = int(body.get("scantime", 12))
    scantime = max(3, min(scantime, 60))
    use_cloud = bool(body.get("use_cloud", True))
    forcescan = bool(body.get("forcescan", True))
    t = threading.Thread(target=_run_scan, args=(scantime, use_cloud, forcescan), daemon=True)
    t.start()
    return jsonify({"started": True})


@app.route("/api/scan/status")
def api_scan_status():
    with _job_lock:
        return jsonify(dict(SCAN_JOB))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@app.route("/api/config", methods=["GET"])
def api_config_get():
    cfg = load_config()
    access_id = cfg.get("access_id", "")
    masked = (access_id[:4] + "..." + access_id[-2:]) if len(access_id) > 8 else ("set" if access_id else "")
    return jsonify({
        "configured": bool(cfg.get("access_id") and cfg.get("access_secret")),
        "access_id_masked": masked,
        "region": cfg.get("region", "us"),
        "regions": REGIONS,
    })


@app.route("/api/config", methods=["POST"])
def api_config_set():
    body = request.get_json(silent=True) or {}
    access_id = (body.get("access_id") or "").strip()
    access_secret = (body.get("access_secret") or "").strip()
    region = (body.get("region") or "us").strip()
    if region not in REGIONS:
        return jsonify({"error": "Unknown region %r" % region}), 400
    cfg = load_config()
    if access_id:
        cfg["access_id"] = access_id
    if access_secret:
        cfg["access_secret"] = access_secret
    cfg["region"] = region
    save_config(cfg)
    return jsonify({"saved": True})


@app.route("/api/config", methods=["DELETE"])
def api_config_clear():
    save_config({"access_id": "", "access_secret": "", "region": "us"})
    return jsonify({"cleared": True})


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------
@app.route("/api/devices", methods=["GET"])
def api_devices_list():
    store = load_devices()
    return jsonify(sorted(store.values(), key=lambda d: (d.get("name") or "").lower()))


@app.route("/api/devices/<dev_id>", methods=["DELETE"])
def api_devices_delete(dev_id):
    store = load_devices()
    if dev_id in store:
        del store[dev_id]
        save_devices(store)
        return jsonify({"deleted": True})
    return jsonify({"error": "not found"}), 404


@app.route("/api/devices/<dev_id>", methods=["PATCH"])
def api_devices_patch(dev_id):
    """Manually edit a device entry (e.g. fix IP, name or paste in a local_key)."""
    store = load_devices()
    entry = store.get(dev_id, {"id": dev_id, "source": "manual"})
    body = request.get_json(silent=True) or {}
    for field in ("name", "ip", "key", "version", "switch_dp"):
        if field in body:
            entry[field] = body[field]
    entry["id"] = dev_id
    store[dev_id] = entry
    save_devices(store)
    return jsonify(entry)


def _get_device_client(entry):
    version = entry.get("version") or "3.3"
    try:
        version = float(version)
    except (TypeError, ValueError):
        version = 3.3
    dev = tinytuya.OutletDevice(
        dev_id=entry["id"],
        address=entry.get("ip") or None,
        local_key=entry.get("key", ""),
        version=version,
        connection_timeout=4,
    )
    dev.set_socketPersistent(False)
    return dev


@app.route("/api/devices/<dev_id>/status", methods=["GET"])
def api_device_status(dev_id):
    store = load_devices()
    entry = store.get(dev_id)
    if not entry:
        return jsonify({"error": "unknown device"}), 404
    if not entry.get("ip") or not entry.get("key"):
        return jsonify({"error": "device is missing an IP and/or local_key - run a sync, or edit it manually"}), 400
    try:
        client = _get_device_client(entry)
        result = client.status()
        if isinstance(result, dict) and "Error" in result:
            return jsonify({"error": result.get("Error"), "raw": result}), 502
        dps = result.get("dps", {}) if isinstance(result, dict) else {}
        entry["online"] = True
        entry["last_dps"] = dps
        entry["last_seen"] = time.time()
        store[dev_id] = entry
        save_devices(store)
        return jsonify({"dps": dps})
    except Exception as e:  # noqa: BLE001
        entry["online"] = False
        store[dev_id] = entry
        save_devices(store)
        return jsonify({"error": str(e)}), 502


@app.route("/api/devices/<dev_id>/set", methods=["POST"])
def api_device_set(dev_id):
    store = load_devices()
    entry = store.get(dev_id)
    if not entry:
        return jsonify({"error": "unknown device"}), 404
    if not entry.get("ip") or not entry.get("key"):
        return jsonify({"error": "device is missing an IP and/or local_key - run a sync, or edit it manually"}), 400
    body = request.get_json(silent=True) or {}
    dp = str(body.get("dp", entry.get("switch_dp", "1")))
    value = body.get("value")
    if value is None:
        return jsonify({"error": "missing 'value'"}), 400
    try:
        client = _get_device_client(entry)
        result = client.set_value(dp, value, nowait=False)
        if isinstance(result, dict) and result.get("Error"):
            return jsonify({"error": result.get("Error"), "raw": result}), 502
        entry["online"] = True
        entry["last_seen"] = time.time()
        entry.setdefault("last_dps", {})[dp] = value
        entry["switch_dp"] = dp
        store[dev_id] = entry
        save_devices(store)
        return jsonify({"ok": True, "dps": entry["last_dps"]})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 502


@app.route("/api/devices/<dev_id>/toggle", methods=["POST"])
def api_device_toggle(dev_id):
    store = load_devices()
    entry = store.get(dev_id)
    if not entry:
        return jsonify({"error": "unknown device"}), 404
    body = request.get_json(silent=True) or {}
    dp = str(body.get("dp", entry.get("switch_dp", "1")))
    current = (entry.get("last_dps") or {}).get(dp)
    new_value = not current if isinstance(current, bool) else True
    if not entry.get("ip") or not entry.get("key"):
        return jsonify({"error": "device is missing an IP and/or local_key - run a sync, or edit it manually"}), 400
    try:
        client = _get_device_client(entry)
        result = client.set_value(dp, new_value, nowait=False)
        if isinstance(result, dict) and result.get("Error"):
            return jsonify({"error": result.get("Error"), "raw": result}), 502
        entry["online"] = True
        entry["last_seen"] = time.time()
        entry.setdefault("last_dps", {})[dp] = new_value
        entry["switch_dp"] = dp
        store[dev_id] = entry
        save_devices(store)
        return jsonify({"ok": True, "dps": entry["last_dps"]})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG") == "1")
