"""Fire TV Enhanced integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .adb_client import FireTVClient
from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SCREENSHOT_INTERVAL, DOMAIN
from .coordinator import FireTVCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.CAMERA]


def _get_coordinator(hass: HomeAssistant) -> FireTVCoordinator | None:
    for coord in hass.data.get(DOMAIN, {}).values():
        if isinstance(coord, FireTVCoordinator):
            return coord
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = FireTVClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        hass_config_dir=hass.config.config_dir,
    )
    if not await client.connect():
        return False

    coordinator = FireTVCoordinator(
        hass, client,
        name=entry.data.get(CONF_NAME, "firetv"),
        scan_interval=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
        screenshot_interval=entry.options.get("screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL),
    )
    custom_apps = entry.options.get("custom_apps", {})
    if custom_apps:
        coordinator.set_custom_apps(custom_apps)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    if not hass.services.has_service(DOMAIN, "launch_app"):
        async def handle_launch_app(call: ServiceCall) -> None:
            coord = _get_coordinator(hass)
            if coord:
                await coord.client.launch_app(call.data["package"])
                await coord.async_request_refresh()

        async def handle_send_notification(call: ServiceCall) -> None:
            coord = _get_coordinator(hass)
            if coord:
                await coord.client.send_notification(call.data["title"], call.data["message"])

        hass.services.async_register(
            DOMAIN, "launch_app", handle_launch_app,
            schema=vol.Schema({vol.Required("package"): cv.string}),
        )
        hass.services.async_register(
            DOMAIN, "send_notification", handle_send_notification,
            schema=vol.Schema({
                vol.Required("title"): cv.string,
                vol.Required("message"): cv.string,
            }),
        )
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: FireTVCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "launch_app")
        hass.services.async_remove(DOMAIN, "send_notification")
    return unload_ok
