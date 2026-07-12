"""Light platform for Tuya Local Dashboard.

On/off only for now - Tuya brightness/color-temp/RGB DPs vary too much
between products to infer generically without per-product DP maps (this
is the same limitation localtuya's light platform documents). A device
still shows up here with a light icon and toggles correctly; dimming can
be added later as a per-device override if needed.
"""
from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TuyaDashboardCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: TuyaDashboardCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _sync_entities() -> None:
        new_entities = []
        for dev_id, device in coordinator.devices.items():
            if device.get("type") != "light" or dev_id in known_ids:
                continue
            known_ids.add(dev_id)
            new_entities.append(TuyaDashboardLight(coordinator, dev_id))
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class TuyaDashboardLight(CoordinatorEntity[TuyaDashboardCoordinator], LightEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: TuyaDashboardCoordinator, dev_id: str) -> None:
        super().__init__(coordinator)
        self._dev_id = dev_id
        device = coordinator.devices.get(dev_id, {})
        self._dp = str(device.get("switch_dp") or "1")
        self._attr_unique_id = f"{DOMAIN}_{dev_id}_light"
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
