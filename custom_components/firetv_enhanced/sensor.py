"""Sensor entities for Fire TV Enhanced."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FireTVCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FireTVCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        FireTVAppSensor(coordinator, entry),
        FireTVPackageSensor(coordinator, entry),
    ])


class FireTVAppSensor(CoordinatorEntity[FireTVCoordinator], SensorEntity):
    """Shows the friendly name of the running app (e.g. Netflix, YouTube)."""

    _attr_has_entity_name = True
    _attr_name = "Current App"
    _attr_icon = "mdi:application"

    def __init__(self, coordinator: FireTVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_current_app"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def native_value(self) -> str:
        if self.coordinator.data:
            return self.coordinator.data.get("app_name", "Unknown")
        return "Unavailable"

    @property
    def icon(self) -> str:
        if self.coordinator.data:
            return self.coordinator.data.get("app_icon", "mdi:application")
        return "mdi:application"


class FireTVPackageSensor(CoordinatorEntity[FireTVCoordinator], SensorEntity):
    """Shows the raw package name (e.g. com.netflix.ninja).

    Useful for finding package names to use in Custom App Names.
    """

    _attr_has_entity_name = True
    _attr_name = "App Package"
    _attr_icon = "mdi:package-variant"
    # Enabled by default — users need this to find package names for custom mappings
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: FireTVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_app_package"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("app_package")
        return None
