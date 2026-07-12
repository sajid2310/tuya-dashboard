"""The Tuya Local Dashboard integration.

Self-contained by design: this file registers the integration's own
bundled Lovelace panel (served straight from this package's www/ folder)
rather than depending on a separate community card like flex-table-card,
and does its own discovery (rather than depending on LocalTuya or any
other Tuya integration).

Inventory + diagnose only - no switch/fan/light entities. This
integration used to also create control entities, but that meant two
integrations (this one and e.g. LocalTuya) both holding/opening
connections to the same physical device, and Tuya's local protocol only
accepts one active connection per device at a time. If you don't run
another local-control Tuya integration, control still works from the
bundled panel itself (via the set_control service, on demand) - it's
just not exposed as permanent HA entities that could double up with
another integration's.
"""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    PANEL_JS_FILENAME,
    PANEL_URL_PATH,
    SERVICE_DIAGNOSE_DEVICE,
    SERVICE_LIST_DEVICES,
    SERVICE_SET_CONTROL,
)
from .coordinator import TuyaDashboardCoordinator

_LOGGER = logging.getLogger(__name__)

# No entity platforms - see module docstring. Kept as an empty tuple (not
# removed) so async_unload_entry's async_unload_platforms call stays a
# valid no-op rather than needing special-casing.
PLATFORMS: list[str] = []

DIAGNOSE_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})
SET_CONTROL_SCHEMA = vol.Schema({
    vol.Required("device_id"): cv.string,
    vol.Required("dp"): cv.string,
    vol.Required("value"): vol.Any(bool, int, float, str),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = TuyaDashboardCoordinator(hass, entry)
    await coordinator.async_load_stored_devices()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_remove_stale_entities(hass, entry)

    await _async_register_panel(hass)
    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


def _async_remove_stale_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """One-time cleanup for anyone who installed an earlier version of this
    integration that created switch/fan/light entities - remove those
    orphaned registry entries now that this integration no longer creates
    them, so they don't linger as permanently-unavailable entities."""
    registry = er.async_get(hass)
    stale = er.async_entries_for_config_entry(registry, entry.entry_id)
    for entity in stale:
        _LOGGER.info("Removing entity from an earlier version of this integration: %s", entity.entity_id)
        registry.async_remove(entity.entity_id)


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Serve the bundled dashboard JS and register it as a sidebar panel.
    No external card is required - the whole UI ships in this package's
    www/ folder and is loaded directly by the browser (no build step, no
    npm dependency)."""
    marker = f"{DOMAIN}_panel_registered"
    if hass.data.get(marker):
        return

    www_path = Path(__file__).parent / "www"
    url_base = f"/{DOMAIN}_panel"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url_base, str(www_path), False)]
    )
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Tuya Devices",
        sidebar_icon="mdi:power-plug-outline",
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "tuya-dashboard-panel",
                "embed_iframe": False,
                "trust_external": False,
                "module_url": f"{url_base}/{PANEL_JS_FILENAME}",
            }
        },
        require_admin=False,
    )
    hass.data[marker] = True


def _coordinators(hass: HomeAssistant):
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, TuyaDashboardCoordinator):
            yield value


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_LIST_DEVICES):
        return

    async def _handle_list_devices(call: ServiceCall) -> ServiceResponse:
        devices = []
        for coordinator in _coordinators(hass):
            for dev_id, d in coordinator.devices.items():
                devices.append({
                    "device_id": dev_id,
                    "name": d.get("name", dev_id),
                    "status": "online" if d.get("online") else "offline",
                    "ip": d.get("ip", ""),
                    "local_key": d.get("key", ""),
                    "version": d.get("version", ""),
                    "category": d.get("category", ""),
                    "type": d.get("type", "other"),
                    "controls": d.get("controls", []),
                    "last_dps": d.get("last_dps", {}),
                    "last_seen": d.get("last_seen"),
                })
        return {"devices": devices}

    hass.services.async_register(
        DOMAIN, SERVICE_LIST_DEVICES, _handle_list_devices,
        supports_response=SupportsResponse.ONLY,
    )

    async def _handle_diagnose_device(call: ServiceCall) -> ServiceResponse:
        dev_id = call.data["device_id"]
        for coordinator in _coordinators(hass):
            if dev_id in coordinator.devices:
                return await hass.async_add_executor_job(coordinator.diagnose_device, dev_id)
        return {"error": "unknown device"}

    hass.services.async_register(
        DOMAIN, SERVICE_DIAGNOSE_DEVICE, _handle_diagnose_device,
        schema=DIAGNOSE_SCHEMA, supports_response=SupportsResponse.ONLY,
    )

    async def _handle_set_control(call: ServiceCall) -> ServiceResponse:
        dev_id = call.data["device_id"]
        dp = str(call.data["dp"])
        value = call.data["value"]
        for coordinator in _coordinators(hass):
            if dev_id in coordinator.devices:
                result = await hass.async_add_executor_job(coordinator.set_control, dev_id, dp, value)
                # Push the new state to entities immediately rather than
                # waiting for the next poll cycle.
                coordinator.async_set_updated_data(coordinator.devices)
                return result
        return {"error": "unknown device"}

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CONTROL, _handle_set_control,
        schema=SET_CONTROL_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
