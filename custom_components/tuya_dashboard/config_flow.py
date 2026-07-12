"""Config flow for Tuya Local Dashboard.

Cloud credentials are optional, same as the standalone dashboard - LAN
broadcast scanning and manually-entered local_keys still work without
them. This keeps the integration usable even for someone who never sets
up a Tuya IoT Platform project.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DEFAULT_REGION, DEFAULT_SCAN_INTERVAL, DEFAULT_SCANTIME, DOMAIN, REGIONS


class TuyaDashboardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input.get("access_id") or "lan-only")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Tuya Local Dashboard",
                data={
                    "access_id": (user_input.get("access_id") or "").strip(),
                    "access_secret": (user_input.get("access_secret") or "").strip(),
                    "region": user_input.get("region", DEFAULT_REGION),
                },
            )

        schema = vol.Schema({
            vol.Optional("access_id", default=""): str,
            vol.Optional("access_secret", default=""): str,
            vol.Optional("region", default=DEFAULT_REGION): vol.In(REGIONS),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return TuyaDashboardOptionsFlow()


class TuyaDashboardOptionsFlow(config_entries.OptionsFlow):
    """Post-setup options: sync interval and per-sync LAN listen time.

    Note: as of HA 2025.12, OptionsFlow subclasses must not set
    self.config_entry explicitly - the base class provides it.
    """

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(
                "scan_interval",
                default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
            vol.Optional(
                "scantime",
                default=self.config_entry.options.get("scantime", DEFAULT_SCANTIME),
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=60)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
