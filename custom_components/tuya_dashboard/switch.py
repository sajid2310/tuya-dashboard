"""Switch platform for Tuya Local Dashboard.

One entity per gang (DP) on switch/plug-type devices, so a 3-gang wall
switch shows up as 3 real switch entities, usable in automations, voice
assistants, etc. - not just a control button on the bundled panel.
"""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaDashboardCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: TuyaDashboardCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_unique_ids: set[str] = set()

    def _sync_entities() -> None:
        new_entities = []
        for dev_id, device in coordinator.devices.items():
            if device.get("type") not in ("switch", "plug", "other"):
                continue
            for control in device.get("controls", []):
                if control["type"] != "toggle":
                    continue
                unique_id = f"{DOMAIN}_{dev_id}_{control['dp']}"
                if unique_id in known_unique_ids:
                    continue
                known_unique_ids.add(unique_id)
                new_entities.append(TuyaDashboardSwitch(coordinator, dev_id, control))
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class TuyaDashboardSwitch(CoordinatorEntity[TuyaDashboardCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TuyaDashboardCoordinator, dev_id: str, control: dict) -> None:
        super().__init__(coordinator)
        self._dev_id = dev_id
        self._dp = control["dp"]
        label = control.get("label", "Power")
        device = coordinator.devices.get(dev_id, {})
        self._attr_unique_id = f"{DOMAIN}_{dev_id}_{self._dp}"
        self._attr_name = None if label == "Power" else label
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=device.get("name", dev_id),
            manufacturer="Tuya",
            model=device.get("category", "unknown"),
        )

    @property
    def _device(self) -> dict:
        return self.coordinator.devices.get(self._dev_id, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._device.get("ip") and self._device.get("key"))

    @property
    def is_on(self) -> bool | None:
        return (self._device.get("last_dps") or {}).get(self._dp)

    @property
    def extra_state_attributes(self) -> dict:
        d = self._device
        return {
            "ip_address": d.get("ip", ""),
            "device_id": self._dev_id,
            "local_key": d.get("key", ""),
            "protocol_version": d.get("version", ""),
            "category": d.get("category", ""),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set(False)

    async def _async_set(self, value: bool) -> None:
        result = await self.hass.async_add_executor_job(
            self.coordinator.set_control, self._dev_id, self._dp, value
        )
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(result["error"])
        self.async_write_ha_state()
