"""Config flow for Fire TV Enhanced."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .adb_client import FireTVClient
from .const import DEFAULT_PORT, DOMAIN


class FireTVEnhancedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Fire TV Enhanced."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle user step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            name = user_input.get(CONF_NAME, f"Fire TV {host}")

            # Pass HA config dir so the ADB key persists
            config_dir = self.hass.config.config_dir
            client = FireTVClient(host, port, hass_config_dir=config_dir)

            # 30s timeout: user needs time to approve on TV
            if await client.connect(timeout=30.0):
                await client.disconnect()

                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name},
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_NAME, default="Fire TV"): str,
            }),
            errors=errors,
        )
