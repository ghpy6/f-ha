"""Fire TV Enhanced integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .adb_client import FireTVClient
from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_SCREENSHOT_INTERVAL, DOMAIN
from .coordinator import FireTVCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fire TV Enhanced from a config entry."""
    client = FireTVClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )

    if not await client.connect():
        return False

    coordinator = FireTVCoordinator(
        hass,
        client,
        name=entry.data.get(CONF_NAME, "firetv"),
        scan_interval=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
        screenshot_interval=entry.options.get("screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL),
    )

    # Load custom app mappings from options
    custom_apps = entry.options.get("custom_apps", {})
    if custom_apps:
        coordinator.set_custom_apps(custom_apps)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: FireTVCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()
    return unload_ok
