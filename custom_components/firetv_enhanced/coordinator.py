"""Data coordinator for Fire TV Enhanced."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adb_client import FireTVClient
from .const import APP_MAP, DEFAULT_SCAN_INTERVAL, DEFAULT_SCREENSHOT_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FireTVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls Fire TV state and screenshots."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: FireTVClient,
        name: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        screenshot_interval: int = DEFAULT_SCREENSHOT_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.screenshot_data: bytes | None = None
        self._screenshot_interval = screenshot_interval
        self._screenshot_counter = 0
        self._custom_apps: dict[str, str] = {}

    def set_custom_apps(self, apps: dict[str, str]) -> None:
        self._custom_apps = apps

    def get_app_name(self, package: str | None) -> str:
        if not package:
            return "Off"
        if package in self._custom_apps:
            return self._custom_apps[package]
        info = APP_MAP.get(package)
        if info:
            return info["name"]
        parts = package.split(".")
        if len(parts) >= 3:
            return parts[-1].replace("_", " ").title()
        return package

    def get_app_icon(self, package: str | None) -> str:
        if not package:
            return "mdi:television-off"
        info = APP_MAP.get(package)
        return info["icon"] if info else "mdi:application"

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch state from Fire TV."""
        if not self.client.connected:
            connected = await self.client.connect()
            if not connected:
                raise UpdateFailed("Cannot connect to Fire TV")

        # State (screen + app) in one call
        state = await self.client.get_state()
        if state is None:
            raise UpdateFailed("No response from Fire TV")

        package = state.get("app_package")
        screen_on = state.get("screen_on", False)

        data: dict[str, Any] = {
            "screen_on": screen_on,
            "app_package": package,
            "app_name": self.get_app_name(package),
            "app_icon": self.get_app_icon(package),
            "playback_state": "idle",
            "media_title": None,
            "volume": 50,
            "muted": False,
        }

        # Media info + volume (only when screen is on and not on home/screensaver)
        if screen_on and package not in (
            "com.amazon.tv.launcher", "com.amazon.firetv.screensaver", None
        ):
            media = await self.client.get_media_info()
            data["playback_state"] = media.get("playback_state", "idle")
            data["media_title"] = media.get("media_title")

            vol = await self.client.get_volume()
            data["volume"] = vol.get("volume", 50)
            data["muted"] = vol.get("muted", False)

        # Screenshot
        if self._screenshot_interval > 0 and screen_on:
            self._screenshot_counter += 1
            interval = self.update_interval.total_seconds() or 5
            polls_needed = max(1, int(self._screenshot_interval / interval))
            if self._screenshot_counter >= polls_needed:
                self._screenshot_counter = 0
                img = await self.client.screenshot()
                if img and len(img) > 100:
                    self.screenshot_data = img

        return data
