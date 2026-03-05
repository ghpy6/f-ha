"""Sensor entities for Fire TV Enhanced."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import FireTVCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FireTVCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FireTVAppSensor(coordinator, entry), FireTVPackageSensor(coordinator, entry)])

class FireTVAppSensor(CoordinatorEntity[FireTVCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Current App"
    _attr_icon = "mdi:application"
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_current_app"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
    @property
    def native_value(self):
        return self.coordinator.data.get("app_name", "Unknown") if self.coordinator.data else "Unavailable"
    @property
    def icon(self):
        return self.coordinator.data.get("app_icon", "mdi:application") if self.coordinator.data else "mdi:application"

class FireTVPackageSensor(CoordinatorEntity[FireTVCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "App Package"
    _attr_icon = "mdi:package-variant"
    _attr_entity_registry_enabled_default = True
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_app_package"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
    @property
    def native_value(self):
        return self.coordinator.data.get("app_package") if self.coordinator.data else None
