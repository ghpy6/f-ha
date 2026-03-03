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

SERVICE_LAUNCH_APP = "launch_app"
SERVICE_SEND_NOTIFICATION = "send_notification"

LAUNCH_APP_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("package"): cv.string,
})

SEND_NOTIFICATION_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("title"): cv.string,
    vol.Required("message"): cv.string,
})


def _get_coordinator_by_entity(
    hass: HomeAssistant, entity_id: str
) -> FireTVCoordinator | None:
    """Find the coordinator that owns a given entity_id."""
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        if isinstance(coordinator, FireTVCoordinator):
            # Check if entity_id matches any entity under this coordinator
            entity_registry = hass.data.get("entity_registry")
            if entity_registry:
                for entity in entity_registry.entities.get_entries_for_config_entry_id(entry_id):
                    if entity.entity_id == entity_id:
                        return coordinator
            # Fallback: use first coordinator if only one exists
            return coordinator
    return None


def _get_first_coordinator(hass: HomeAssistant) -> FireTVCoordinator | None:
    """Get first available coordinator (for simple setups)."""
    for coord in hass.data.get(DOMAIN, {}).values():
        if isinstance(coord, FireTVCoordinator):
            return coord
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fire TV Enhanced from a config entry."""
    client = FireTVClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        hass_config_dir=hass.config.config_dir,
    )

    if not await client.connect():
        return False

    coordinator = FireTVCoordinator(
        hass,
        client,
        name=entry.data.get(CONF_NAME, "firetv"),
        scan_interval=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
        screenshot_interval=entry.options.get(
            "screenshot_interval", DEFAULT_SCREENSHOT_INTERVAL
        ),
        cec_enabled=entry.options.get("cec_enabled", True),
    )

    custom_apps = entry.options.get("custom_apps", {})
    if custom_apps:
        coordinator.set_custom_apps(custom_apps)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Register services (only once across all entries)
    if not hass.services.has_service(DOMAIN, SERVICE_LAUNCH_APP):
        async def handle_launch_app(call: ServiceCall) -> None:
            coord = _get_first_coordinator(hass)
            if coord:
                await coord.client.launch_app(call.data["package"])
                await coord.async_request_refresh()

        async def handle_send_notification(call: ServiceCall) -> None:
            coord = _get_first_coordinator(hass)
            if coord:
                await coord.client.send_notification(
                    call.data["title"], call.data["message"]
                )

        hass.services.async_register(
            DOMAIN, SERVICE_LAUNCH_APP, handle_launch_app, schema=LAUNCH_APP_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_SEND_NOTIFICATION, handle_send_notification,
            schema=SEND_NOTIFICATION_SCHEMA,
        )

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when user changes settings."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: FireTVCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()

    # Unregister services if no entries left
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_LAUNCH_APP)
        hass.services.async_remove(DOMAIN, SERVICE_SEND_NOTIFICATION)

    return unload_ok
