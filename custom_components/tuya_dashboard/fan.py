"""Fan platform for Tuya Local Dashboard."""
from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAN_SPEED_DP, FAN_SWITCH_DP
from .coordinator import TuyaDashboardCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: TuyaDashboardCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _sync_entities() -> None:
        new_entities = []
        for dev_id, device in coordinator.devices.items():
            if device.get("type") != "fan" or dev_id in known_ids:
                continue
            known_ids.add(dev_id)
            new_entities.append(TuyaDashboardFan(coordinator, dev_id))
        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_sync_entities))


class TuyaDashboardFan(CoordinatorEntity[TuyaDashboardCoordinator], FanEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_speed_count = 100

    def __init__(self, coordinator: TuyaDashboardCoordinator, dev_id: str) -> None:
        super().__init__(coordinator)
        self._dev_id = dev_id
        device = coordinator.devices.get(dev_id, {})
        self._attr_unique_id = f"{DOMAIN}_{dev_id}_fan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            name=device.get("name", dev_id),
            manufacturer="Tuya",
            model=device.get("category", "unknown"),
        )
        has_speed = any(
            c["dp"] == FAN_SPEED_DP for c in device.get("controls", []) if c["type"] == "stepper"
        )
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED if has_speed else FanEntityFeature(0)
        )

    @property
    def _device(self) -> dict:
        return self.coordinator.devices.get(self._dev_id, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._device.get("ip") and self._device.get("key"))

    @property
    def is_on(self) -> bool | None:
        return (self._device.get("last_dps") or {}).get(FAN_SWITCH_DP)

    @property
    def percentage(self) -> int | None:
        val = (self._device.get("last_dps") or {}).get(FAN_SPEED_DP)
        try:
            return max(0, min(100, int(val)))
        except (TypeError, ValueError):
            return None

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

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs) -> None:
        await self._async_set_dp(FAN_SWITCH_DP, True)
        if percentage is not None:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set_dp(FAN_SWITCH_DP, False)

    async def async_set_percentage(self, percentage: int) -> None:
        await self._async_set_dp(FAN_SPEED_DP, max(1, percentage))

    async def _async_set_dp(self, dp: str, value) -> None:
        result = await self.hass.async_add_executor_job(
            self.coordinator.set_control, self._dev_id, dp, value
        )
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(result["error"])
        self.async_write_ha_state()
