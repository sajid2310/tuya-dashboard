"""DataUpdateCoordinator for Tuya Local Dashboard.

Ports the same discovery techniques as the standalone dashboard (app.py in
the repo root) into Home Assistant's update-coordinator pattern:

  1. LAN broadcast scan (tinytuya.scanner.devices) - listens for the UDP
     broadcast packets Tuya devices send out (ports 6666/6667/7000).
  2. Tuya Cloud API (tinytuya.Cloud) - optional; gives device names,
     categories and local_keys if you provide Access ID/Secret.
  3. MAC/ARP sweep - for cloud-known devices the broadcast scan missed,
     probes local subnets on port 6668 and cross-references the OS ARP
     table to resolve a current IP from a known MAC address.

All of this is blocking/synchronous (raw sockets, subprocess calls), so it
always runs via hass.async_add_executor_job - never directly on the event
loop.
"""
from __future__ import annotations

import concurrent.futures
import ipaddress
import logging
import re
import socket
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import tinytuya
from tinytuya import scanner

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CATEGORY_TYPES,
    DEFAULT_LOCAL_POLLING,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCANTIME,
    FAN_SPEED_DP,
    FAN_SWITCH_DP,
    GANG_SWITCH_DPS,
    MAX_NETWORKS_SWEPT,
    MAX_SWEEP_HOSTS_PER_NET,
    TUYA_LOCAL_PORT,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

_ARP_LINE_RE = re.compile(
    r"\(?(\d{1,3}(?:\.\d{1,3}){3})\)?\s+at\s+([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})"
)


def _normalize_mac(mac: str) -> str:
    hexonly = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(hexonly) != 12:
        return ""
    return ":".join(hexonly[i:i + 2] for i in range(0, 12, 2)).lower()


def device_type(entry: dict) -> str:
    cat = (entry.get("category") or "").lower()
    return CATEGORY_TYPES.get(cat, "other")


def controls_for_entry(entry: dict) -> list[dict]:
    """Describe what controls should exist for a device - one toggle per
    gang for multi-gang switches/plugs, power+speed for fans, a single
    generic toggle otherwise. Mirrors the standalone dashboard exactly."""
    dtype = device_type(entry)
    dps = entry.get("last_dps") or {}

    if dtype == "fan":
        controls = [{"type": "toggle", "dp": FAN_SWITCH_DP, "label": "Power"}]
        if FAN_SPEED_DP in dps:
            controls.append({"type": "stepper", "dp": FAN_SPEED_DP, "label": "Speed"})
        return controls

    if dtype in ("switch", "plug"):
        gangs = [dp for dp in GANG_SWITCH_DPS if isinstance(dps.get(dp), bool)]
        if gangs:
            multi = len(gangs) > 1
            return [
                {"type": "toggle", "dp": dp, "label": ("Gang %s" % dp) if multi else "Power"}
                for dp in gangs
            ]
        default_dp = str(entry.get("switch_dp") or "1")
        return [{"type": "toggle", "dp": default_dp, "label": "Power"}]

    default_dp = str(entry.get("switch_dp") or "1")
    return [{"type": "toggle", "dp": default_dp, "label": "Power"}]


class TuyaDashboardCoordinator(DataUpdateCoordinator):
    """Coordinates discovery + polling for one config entry (one Tuya
    Cloud account, or LAN-only if no cloud credentials were given)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, f"tuya_dashboard_{entry.entry_id}")
        self.devices: dict[str, dict] = {}
        interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name="Tuya Local Dashboard",
            update_interval=timedelta(seconds=interval),
        )

    async def async_load_stored_devices(self) -> None:
        """Load previously discovered devices (name/ip/local_key/etc) from
        HA's storage dir so entities aren't blank on restart, before the
        first live sync completes."""
        stored = await self._store.async_load()
        if stored:
            self.devices = stored

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            devices = await self.hass.async_add_executor_job(self._sync_blocking)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Tuya sync failed: {err}") from err
        await self._store.async_save(devices)
        self.devices = devices
        return devices

    # -- the blocking sync itself (runs in the executor) --------------------
    def _sync_blocking(self) -> dict[str, dict]:
        data = self.entry.data
        options = self.entry.options

        cloud_list: list[dict] = []
        cloud = None
        if data.get("access_id") and data.get("access_secret"):
            try:
                cloud = tinytuya.Cloud(
                    apiRegion=data.get("region", "us"),
                    apiKey=data["access_id"],
                    apiSecret=data["access_secret"],
                )
                raw = cloud.getdevices()
                if isinstance(raw, list):
                    cloud_list = raw
                else:
                    _LOGGER.warning("Tuya Cloud API returned an unexpected response: %r", raw)
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Tuya Cloud API request failed: %s", e)

        local_polling = bool(options.get("local_polling", DEFAULT_LOCAL_POLLING))

        scantime = int(options.get("scantime", DEFAULT_SCANTIME))
        # Force-scanning opens a real connection to every cloud-known device
        # to do a protocol handshake - only do this if local polling is
        # explicitly enabled (see DEFAULT_LOCAL_POLLING). Otherwise we stay
        # purely passive: just listen for the UDP broadcasts devices already
        # send out, which never touches a device's local TCP port.
        forcescan_enabled = bool(cloud_list) and local_polling
        scan_kwargs = dict(
            byID=True,
            tuyadevices=cloud_list,
            scantime=scantime,
            color=False,
            poll=False,
            verbose=False,
            # Never let tinytuya fall back to input() - this always runs
            # headless inside HA's executor, there is no stdin.
            assume_yes=True,
        )
        found: dict = {}
        try:
            found = scanner.devices(forcescan=forcescan_enabled, **scan_kwargs) or {}
        except OSError as e:
            if not forcescan_enabled:
                _LOGGER.warning("LAN broadcast scan failed: %s", e)
            else:
                _LOGGER.warning(
                    "Force-scan hit a network hiccup (%s), retrying without it", type(e).__name__
                )
                try:
                    found = scanner.devices(forcescan=False, **scan_kwargs) or {}
                except OSError as e2:
                    _LOGGER.warning("Broadcast-only scan also failed: %s", e2)

        mac_ip_map: dict[str, str] = {}
        if cloud_list:
            found_ids = set(found.keys())
            sweep_targets = [
                dev["mac"] for dev in cloud_list
                if dev.get("id") not in found_ids and dev.get("mac")
            ]
            if sweep_targets:
                try:
                    mac_ip_map = self._find_ips_by_mac(sweep_targets)
                except Exception as e:  # noqa: BLE001
                    _LOGGER.warning("MAC/ARP sweep failed: %s", e)

        merged = self._merge(found, cloud_list, mac_ip_map)

        # Broadcast-only discovery is inherently unreliable for "online" -
        # devices don't broadcast on every window, and with force-scan off
        # by default there's no active handshake to confirm reachability
        # either. Tuya Cloud's per-device connect-status check fixes this
        # without touching the device at all (it's a cloud-side API call,
        # same as the Diagnose button's cloud check) - so it's always safe
        # to run, regardless of the local_polling setting.
        if cloud is not None and cloud_list:
            # Broadcast-confirmed devices this cycle are already known-good;
            # only ask the cloud about the rest so a momentary cloud-side
            # lag can't override a device we just heard from directly.
            already_confirmed = set((found or {}).keys())
            check_ids = [d["id"] for d in cloud_list if d.get("id") and d["id"] not in already_confirmed]
            if check_ids:
                self._refresh_cloud_online_status(cloud, merged, check_ids)

        # Per-device status polling opens a real connection to read DPs
        # (needed to detect gang count / fan speed / current on-off state).
        # Same reasoning as force-scan above: only do this automatically if
        # local polling is enabled. Otherwise entities just start as
        # "unknown" until something triggers a real connection on demand
        # (a manual toggle, the Diagnose button, or a status refresh) -
        # rare, user-initiated connections don't fight another integration's
        # persistent one the way a full-fleet poll every couple of minutes
        # does.
        if local_polling:
            pollable = [
                dev_id for dev_id, entry in merged.items()
                if entry.get("ip") and entry.get("key")
            ]
            if pollable:
                self._poll_devices_for_dps(merged, pollable)

        for dev_id, entry in merged.items():
            entry["type"] = device_type(entry)
            entry["controls"] = controls_for_entry(entry)

        return merged

    def _merge(self, scanned_by_id: dict, cloud_list: list, mac_ip_map: dict) -> dict:
        store = {k: dict(v) for k, v in self.devices.items()}
        now = time.time()
        mac_ip_map = mac_ip_map or {}

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
                "source": "cloud",
            })
            if dev.get("version"):
                entry["version"] = dev.get("version")
            store[dev_id] = entry

        for dev_id, info in (scanned_by_id or {}).items():
            entry = store.get(dev_id, {})
            entry.update({
                "id": dev_id,
                "ip": info.get("ip", entry.get("ip", "")),
                "version": info.get("version") or entry.get("version", "3.3"),
                "mac": info.get("mac") or entry.get("mac", ""),
                "online": True,
                "last_seen": now,
                "origin": info.get("origin", "broadcast"),
            })
            if not entry.get("name"):
                entry["name"] = info.get("name") or dev_id
            if not entry.get("key"):
                entry["key"] = info.get("key", "")
            store[dev_id] = entry

        matched_by_sweep = set()
        if mac_ip_map:
            for dev_id, entry in store.items():
                if dev_id in (scanned_by_id or {}):
                    continue
                mac = _normalize_mac(entry.get("mac", ""))
                if mac and mac in mac_ip_map:
                    entry["ip"] = mac_ip_map[mac]
                    entry["online"] = True
                    entry["last_seen"] = now
                    entry["origin"] = "mac_sweep"
                    store[dev_id] = entry
                    matched_by_sweep.add(dev_id)

        seen_ids = set((scanned_by_id or {}).keys()) | matched_by_sweep
        for dev_id, entry in store.items():
            if dev_id not in seen_ids:
                entry["online"] = False

        return store

    def _refresh_cloud_online_status(self, cloud, store: dict, dev_ids: list[str], max_workers=5) -> None:
        """Ask Tuya Cloud (not the device) whether each device is online.
        This is the same call the Diagnose button uses for its cloud check
        - a plain HTTPS request to Tuya's API, never a connection to the
        device itself - so it's always safe to run in the background
        regardless of what other integrations are doing locally."""
        def _check_one(dev_id: str) -> None:
            try:
                status = cloud.getconnectstatus(dev_id)
            except Exception:  # noqa: BLE001
                return
            if isinstance(status, dict) and status.get("Error"):
                return
            entry = store.get(dev_id)
            if entry is not None:
                entry["online"] = bool(status)
                if status:
                    entry["last_seen"] = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            list(ex.map(_check_one, dev_ids))

    def _poll_devices_for_dps(self, store: dict, dev_ids: list[str], max_workers=8, timeout=3) -> None:
        def _poll_one(dev_id: str) -> None:
            entry = store.get(dev_id)
            if not entry or not entry.get("ip") or not entry.get("key"):
                return
            try:
                version = float(entry.get("version") or 3.3)
            except (TypeError, ValueError):
                version = 3.3
            try:
                client = tinytuya.OutletDevice(
                    dev_id=entry["id"],
                    address=entry.get("ip"),
                    local_key=entry.get("key", ""),
                    version=version,
                    connection_timeout=timeout,
                )
                client.set_socketPersistent(False)
                result = client.status()
                if isinstance(result, dict) and "dps" in result:
                    entry["last_dps"] = result["dps"]
            except Exception:  # noqa: BLE001
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            list(ex.map(_poll_one, dev_ids))

    # -- MAC/ARP sweep --------------------------------------------------
    def _local_ipv4_networks(self) -> list:
        import psutil

        nets = []
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
        seen, uniq = set(), []
        for n in nets:
            if str(n) not in seen:
                seen.add(str(n))
                uniq.append(n)
        return uniq[:MAX_NETWORKS_SWEPT]

    def _tcp_probe(self, ip, port=TUYA_LOCAL_PORT, timeout=0.35) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((str(ip), port)) == 0
        except OSError:
            return False

    def _sweep_networks(self, networks, max_workers=128) -> list[str]:
        hosts = []
        for net in networks:
            hosts.extend(net.hosts())
        if not hosts:
            return []
        responsive = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self._tcp_probe, h): h for h in hosts}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    if fut.result():
                        responsive.append(str(futures[fut]))
                except Exception:  # noqa: BLE001
                    pass
        return responsive

    def _read_arp_table(self) -> dict[str, str]:
        table: dict[str, str] = {}
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
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                m = _ARP_LINE_RE.search(line)
                if m:
                    table[m.group(1)] = _normalize_mac(m.group(2))
        except Exception:  # noqa: BLE001
            pass
        return table

    def _find_ips_by_mac(self, target_macs: list[str]) -> dict[str, str]:
        wanted = {_normalize_mac(m) for m in target_macs if m}
        wanted.discard("")
        if not wanted:
            return {}
        networks = self._local_ipv4_networks()
        if not networks:
            return {}
        self._sweep_networks(networks)
        arp = self._read_arp_table()
        return {mac: ip for ip, mac in arp.items() if mac in wanted}

    # -- device control / diagnostics -----------------------------------
    def get_device_client(self, dev_id: str):
        entry = self.devices.get(dev_id)
        if not entry or not entry.get("ip") or not entry.get("key"):
            return None
        try:
            version = float(entry.get("version") or 3.3)
        except (TypeError, ValueError):
            version = 3.3
        client = tinytuya.OutletDevice(
            dev_id=entry["id"],
            address=entry.get("ip"),
            local_key=entry.get("key", ""),
            version=version,
            connection_timeout=4,
        )
        client.set_socketPersistent(False)
        return client

    def set_control(self, dev_id: str, dp: str, value) -> dict:
        """Runs in the executor. Sets one DP on one device - the backing
        call for the tuya_dashboard.set_control service and for the
        switch/fan/light entity platforms."""
        client = self.get_device_client(dev_id)
        if client is None:
            return {"error": "Device is missing an IP and/or local_key - wait for the next sync."}
        try:
            result = client.set_value(dp, value, nowait=False)
            if isinstance(result, dict) and result.get("Error"):
                return {"error": result.get("Error")}
            entry = self.devices.setdefault(dev_id, {})
            entry.setdefault("last_dps", {})[dp] = value
            entry["online"] = True
            entry["last_seen"] = time.time()
            return {"ok": True, "dps": entry["last_dps"]}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def diagnose_device(self, dev_id: str) -> dict:
        """Runs in the executor. Independently checks local (LAN) and Tuya
        Cloud connectivity for one device - port of the standalone
        dashboard's /api/devices/<id>/diagnose endpoint."""
        entry = self.devices.get(dev_id)
        if not entry:
            return {"error": "unknown device"}

        result: dict = {
            "checked_at": time.time(),
            "local": {"ok": False, "detail": None},
            "cloud": {"ok": False, "detail": None},
        }

        if not entry.get("ip") or not entry.get("key"):
            result["local"]["detail"] = "No IP/local_key on file yet - wait for the next sync."
        else:
            try:
                client = self.get_device_client(dev_id)
                status = client.status()
                if isinstance(status, dict) and status.get("Error"):
                    result["local"]["detail"] = status.get("Error")
                elif isinstance(status, dict) and "dps" in status:
                    result["local"]["ok"] = True
                    result["local"]["detail"] = "Responded locally on %s" % entry.get("ip")
                    entry["online"] = True
                    entry["last_dps"] = status.get("dps", entry.get("last_dps", {}))
                    entry["last_seen"] = time.time()
                else:
                    result["local"]["detail"] = "Unexpected response: %r" % (status,)
            except Exception as e:  # noqa: BLE001
                result["local"]["detail"] = str(e)

        data = self.entry.data
        if not (data.get("access_id") and data.get("access_secret")):
            result["cloud"]["detail"] = "No Tuya Cloud credentials configured for this entry."
        else:
            try:
                cloud = tinytuya.Cloud(
                    apiRegion=data.get("region", "us"),
                    apiKey=data["access_id"],
                    apiSecret=data["access_secret"],
                )
                status = cloud.getconnectstatus(dev_id)
                if isinstance(status, dict) and status.get("Error"):
                    result["cloud"]["detail"] = status.get("Error")
                else:
                    online = bool(status)
                    result["cloud"]["ok"] = online
                    result["cloud"]["detail"] = (
                        "Cloud reports device online" if online else "Cloud reports device offline"
                    )
            except Exception as e:  # noqa: BLE001
                result["cloud"]["detail"] = str(e)

        if result["local"]["ok"] and result["cloud"]["ok"]:
            result["verdict"] = "both_ok"
            result["hint"] = "Both local and cloud connectivity are working - the device itself is healthy."
        elif result["local"]["ok"] and not result["cloud"]["ok"]:
            result["verdict"] = "cloud_issue"
            result["hint"] = (
                "Local control works, but Tuya's cloud doesn't see the device as online. "
                "This looks like a cloud/internet issue on the device's side, not this integration."
            )
        elif not result["local"]["ok"] and result["cloud"]["ok"]:
            result["verdict"] = "local_issue"
            result["hint"] = (
                "Tuya's cloud sees the device as online, but Home Assistant can't reach it locally. "
                "This looks like a local-network issue - confirm HA and the device are on the same "
                "subnet/VLAN and that nothing is blocking port 6668."
            )
        else:
            result["verdict"] = "both_down"
            result["hint"] = (
                "Neither local nor cloud connectivity is working - the device is likely powered off, "
                "disconnected from WiFi, or has an outdated local_key."
            )

        return result
