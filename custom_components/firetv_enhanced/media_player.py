"""Media player entity for Fire TV Enhanced."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import APP_MAP, DOMAIN
from .coordinator import FireTVCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FireTVCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FireTVMediaPlayer(coordinator, entry)])


class FireTVMediaPlayer(CoordinatorEntity[FireTVCoordinator], MediaPlayerEntity):
    """Fire TV media player."""

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
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: FireTVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Fire TV"),
            "manufacturer": "Amazon",
            "model": "Fire TV",
        }

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

        # App is open but no active playback detected
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("media_title")
        return None

    @property
    def media_content_type(self) -> MediaType | None:
        """Detect if it's music or video based on the app."""
        app = self.app_id
        if not app:
            return None
        music_apps = ("com.spotify.tv.android", "com.amazon.music.tv")
        if app in music_apps:
            return MediaType.MUSIC
        return MediaType.VIDEO

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
        return sorted({v["name"] for v in APP_MAP.values()})

    @property
    def icon(self) -> str:
        if self.coordinator.data:
            return self.coordinator.data.get("app_icon", "mdi:television")
        return "mdi:television"

    @property
    def volume_level(self) -> float | None:
        if self.coordinator.data:
            return self.coordinator.data.get("volume", 50) / 100
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        if self.coordinator.data:
            return self.coordinator.data.get("muted", False)
        return None

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

    async def async_volume_up(self) -> None:
        await self.coordinator.client.volume_up()
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        await self.coordinator.client.volume_down()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.client.set_volume(int(volume * 15))
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.client.volume_mute()
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        for pkg, info in APP_MAP.items():
            if info["name"] == source:
                await self.coordinator.client.launch_app(pkg)
                await self.coordinator.async_request_refresh()
                return
