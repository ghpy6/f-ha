"""Camera entity for Fire TV Enhanced — serves 16:9 screenshots."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FireTVCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FireTVCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FireTVCamera(coordinator, entry)])


class FireTVCamera(CoordinatorEntity[FireTVCoordinator], Camera):
    """Fire TV screen as a camera entity."""

    _attr_has_entity_name = True
    _attr_name = "Screen"
    _attr_icon = "mdi:monitor-screenshot"
    _attr_frame_interval = 10

    def __init__(self, coordinator: FireTVCoordinator, entry: ConfigEntry) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self.content_type = "image/png"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data:
            return self.coordinator.data.get("screen_on", False)
        return False

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        data = self.coordinator.screenshot_data
        if data and len(data) > 100 and data[:4] == b'\x89PNG':
            return data
        return None
