"""Config flow for Fire TV Enhanced."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .adb_client import FireTVClient
from .const import APP_MAP, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SCREENSHOT_INTERVAL, DOMAIN


class FireTVEnhancedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._user_data: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._user_data = user_input
            return await self.async_step_confirm_tv()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_NAME, default="Fire TV"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
        )

    async def async_step_confirm_tv(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = self._user_data[CONF_HOST]
            port = self._user_data.get(CONF_PORT, DEFAULT_PORT)
            name = self._user_data.get(CONF_NAME, f"Fire TV {host}")

            client = FireTVClient(host, port, hass_config_dir=self.hass.config.config_dir)
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
            step_id="confirm_tv",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FireTVOptionsFlow(config_entry)


class FireTVOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    def _build_app_list_text(self) -> str:
        """Build a readable list of all known apps for the description."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        custom = self._config_entry.options.get("custom_apps", {})
        lines = []

        # Discovered apps
        discovered = []
        if coordinator and hasattr(coordinator, "discovered_packages"):
            discovered = coordinator.discovered_packages or []

        # All known packages: discovered + built-in keys
        all_pkgs = set(discovered) | set(APP_MAP.keys())
        # Remove non-launchable
        skip = {"com.amazon.tv.launcher", "com.amazon.firetv.screensaver",
                "com.amazon.tv.settings", "com.amazon.tv.notificationcenter"}
        all_pkgs -= skip

        for pkg in sorted(all_pkgs):
            if pkg in custom:
                name = custom[pkg]
                lines.append(f"  \u2705 {pkg} = {name}")
            elif pkg in APP_MAP:
                name = APP_MAP[pkg]["name"]
                lines.append(f"  \u2022 {pkg} \u2192 {name}")
            else:
                parts = pkg.split(".")
                auto_name = parts[-1].replace("_", " ").title() if len(parts) >= 2 else pkg
                lines.append(f"  \u2022 {pkg} \u2192 {auto_name}")

        return "\n".join(lines) if lines else "  No apps discovered yet"

    def _build_custom_text_default(self) -> str:
        """Pre-populate with current custom overrides."""
        custom = self._config_entry.options.get("custom_apps", {})
        stored_text = self._config_entry.options.get("custom_apps_text", "")
        if stored_text:
            return stored_text
        if custom:
            return "\n".join(f"{pkg} = {name}" for pkg, name in sorted(custom.items()))
        return ""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            new_options = dict(self._config_entry.options)
            new_options["scan_interval"] = int(
                user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            )
            new_options["screenshot_interval"] = int(
                user_input.get("screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL)
            )

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
            new_options["custom_apps_text"] = raw
            return self.async_create_entry(title="", data=new_options)

        opts = self._config_entry.options
        app_list = self._build_app_list_text()
        custom_default = self._build_custom_text_default()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "scan_interval",
                    default=opts.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(NumberSelectorConfig(
                    min=1, max=60, step=1,
                    unit_of_measurement="seconds",
                    mode=NumberSelectorMode.BOX,
                )),
                vol.Optional(
                    "screenshot_interval",
                    default=opts.get("screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL),
                ): NumberSelector(NumberSelectorConfig(
                    min=1, max=120, step=1,
                    unit_of_measurement="seconds",
                    mode=NumberSelectorMode.BOX,
                )),
                vol.Optional(
                    "custom_apps_text",
                    default=custom_default,
                ): TextSelector(TextSelectorConfig(
                    multiline=True,
                    type=TextSelectorType.TEXT,
                )),
            }),
            description_placeholders={
                "app_list": app_list,
            },
        )
