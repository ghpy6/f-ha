"""Media player entity for Fire TV Enhanced."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity, MediaPlayerEntityFeature,
    MediaPlayerState, MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FireTVCoordinator

MUSIC_APPS = {
    "com.spotify.tv.android", "com.amazon.music.tv",
    "com.apple.android.music", "com.deezer.tv",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FireTVCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FireTVMediaPlayer(coordinator, entry)])


class FireTVMediaPlayer(CoordinatorEntity[FireTVCoordinator], MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: FireTVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, "Fire TV"),
            manufacturer="Amazon",
            model="Fire TV Stick",
        )
        self._camera_entity_id: str | None = None

    @property
    def entity_picture(self) -> str | None:
        """Show live screenshot in the media player card."""
        if not self.coordinator.screenshot_data:
            return None
        if not self.coordinator.data or not self.coordinator.data.get("screen_on"):
            return None
        # Find camera entity_id from registry (only once)
        if self._camera_entity_id is None:
            ent_reg = er.async_get(self.hass)
            camera_uid = f"{self._entry.entry_id}_camera"
            self._camera_entity_id = ent_reg.async_get_entity_id(
                "camera", DOMAIN, camera_uid
            ) or ""
        if self._camera_entity_id:
            return f"/api/camera_proxy/{self._camera_entity_id}"
        return None

    @property
    def state(self) -> MediaPlayerState:
        data = self.coordinator.data
        if not data or not data.get("screen_on"):
            return MediaPlayerState.OFF
        app = data.get("app_package", "")
        if app in ("com.amazon.tv.launcher", "com.amazon.firetv.screensaver", None):
            return MediaPlayerState.IDLE
        playback = data.get("playback_state", "idle")
        if playback == "playing":
            return MediaPlayerState.PLAYING
        if playback == "paused":
            return MediaPlayerState.PAUSED
        if playback == "buffering":
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.ON

    @property
    def media_title(self) -> str | None:
        if self.coordinator.data:
            title = self.coordinator.data.get("media_title")
            return title if title else self.coordinator.data.get("app_name")
        return None

    @property
    def media_content_type(self) -> MediaType | None:
        app = self.app_id
        if not app:
            return None
        return MediaType.MUSIC if app in MUSIC_APPS else MediaType.VIDEO

    @property
    def app_id(self) -> str | None:
        return self.coordinator.data.get("app_package") if self.coordinator.data else None

    @property
    def app_name(self) -> str | None:
        return self.coordinator.data.get("app_name") if self.coordinator.data else None

    @property
    def source(self) -> str | None:
        return self.app_name

    @property
    def source_list(self) -> list[str]:
        return self.coordinator.get_source_list()

    @property
    def icon(self) -> str:
        if self.coordinator.data:
            return self.coordinator.data.get("app_icon", "mdi:television")
        return "mdi:television"

    async def async_turn_on(self) -> None:
        await self.coordinator.client.turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.coordinator.client.turn_off()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        await self.coordinator.client.media_play()
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        await self.coordinator.client.media_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        await self.coordinator.client.media_stop()
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        await self.coordinator.client.media_next()
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        await self.coordinator.client.media_previous()
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        pkg = self.coordinator.get_package_for_source(source)
        if pkg:
            await self.coordinator.client.launch_app(pkg)
            await self.coordinator.async_request_refresh()
