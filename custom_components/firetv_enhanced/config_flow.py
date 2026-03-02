"""Config flow for Fire TV Enhanced."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

from .adb_client import FireTVClient
from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SCREENSHOT_INTERVAL, DOMAIN


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

            config_dir = self.hass.config.config_dir
            client = FireTVClient(host, port, hass_config_dir=config_dir)

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options flow for editing settings after install."""
        return FireTVOptionsFlow(config_entry)


class FireTVOptionsFlow(config_entries.OptionsFlow):
    """Options flow — edit app names, intervals, etc."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Main options menu."""
        if user_input is not None:
            # Save options
            new_options = dict(self._config_entry.options)
            new_options["scan_interval"] = user_input.get(
                "scan_interval", DEFAULT_SCAN_INTERVAL
            )
            new_options["screenshot_interval"] = user_input.get(
                "screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL
            )
            new_options["custom_apps_text"] = user_input.get("custom_apps_text", "")

            # Parse custom apps text → dict
            custom_apps = {}
            raw = user_input.get("custom_apps_text", "")
            for line in raw.strip().splitlines():
                line = line.strip()
                if "=" in line:
                    pkg, name = line.split("=", 1)
                    pkg = pkg.strip()
                    name = name.strip()
                    if pkg and name:
                        custom_apps[pkg] = name
            new_options["custom_apps"] = custom_apps

            return self.async_create_entry(title="", data=new_options)

        # Current values
        opts = self._config_entry.options
        current_custom = opts.get("custom_apps", {})
        custom_text = "\n".join(
            f"{pkg} = {name}" for pkg, name in current_custom.items()
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "scan_interval",
                    default=opts.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=2, max=60)),
                vol.Optional(
                    "screenshot_interval",
                    default=opts.get("screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL),
                ): vol.All(int, vol.Range(min=5, max=120)),
                vol.Optional(
                    "custom_apps_text",
                    default=custom_text,
                ): str,
            }),
        )
