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

_SKIP_SOURCES = {
    "com.amazon.tv.launcher", "com.amazon.firetv.screensaver",
    "com.amazon.tv.settings", "com.amazon.tv.notificationcenter",
}


class FireTVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls Fire TV state, screenshots, and manages app discovery."""

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
        self._discovered_packages: list[str] = []
        self._discovery_done = False
        self._update_count = 0

    def set_custom_apps(self, apps: dict[str, str]) -> None:
        self._custom_apps = apps

    @property
    def discovered_packages(self) -> list[str]:
        return self._discovered_packages

    def _build_full_app_map(self) -> dict[str, dict[str, str]]:
        full: dict[str, dict[str, str]] = {}
        full.update(APP_MAP)
        for pkg in self._discovered_packages:
            if pkg not in full:
                parts = pkg.split(".")
                name = parts[-1].replace("_", " ").title() if len(parts) >= 2 else pkg
                full[pkg] = {"name": name, "icon": "mdi:application"}
        for pkg, name in self._custom_apps.items():
            if pkg in full:
                full[pkg] = {"name": name, "icon": full[pkg].get("icon", "mdi:application")}
            else:
                full[pkg] = {"name": name, "icon": "mdi:application"}
        return full

    def get_app_name(self, package: str | None) -> str:
        if not package:
            return "Off"
        full = self._build_full_app_map()
        info = full.get(package)
        if info:
            return info["name"]
        parts = package.split(".")
        if len(parts) >= 3:
            return parts[-1].replace("_", " ").title()
        return package

    def get_app_icon(self, package: str | None) -> str:
        if not package:
            return "mdi:television-off"
        full = self._build_full_app_map()
        info = full.get(package)
        return info["icon"] if info else "mdi:application"

    def get_source_list(self) -> list[str]:
        full = self._build_full_app_map()
        return sorted(v["name"] for k, v in full.items() if k not in _SKIP_SOURCES)

    def get_package_for_source(self, source: str) -> str | None:
        full = self._build_full_app_map()
        for pkg, info in full.items():
            if info["name"] == source:
                return pkg
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        if not self.client.connected:
            connected = await self.client.connect()
            if not connected:
                raise UpdateFailed("Cannot connect to Fire TV")

        # App discovery: once at start, then every ~100 polls
        if not self._discovery_done:
            try:
                self._discovered_packages = await self.client.discover_apps()
                self._discovery_done = True
                _LOGGER.info("Discovered %d installed apps", len(self._discovered_packages))
            except Exception as err:
                _LOGGER.debug("App discovery failed: %s", err)

        self._update_count += 1
        if self._update_count >= 100:
            self._update_count = 0
            try:
                self._discovered_packages = await self.client.discover_apps()
            except Exception:
                pass

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
        }

        if screen_on and package not in (
            "com.amazon.tv.launcher", "com.amazon.firetv.screensaver", None
        ):
            media = await self.client.get_media_info()
            data["playback_state"] = media.get("playback_state", "idle")
            data["media_title"] = media.get("media_title")

        if self._screenshot_interval > 0 and screen_on:
            self._screenshot_counter += 1
            interval = self.update_interval.total_seconds() or 5
            polls_needed = max(1, int(self._screenshot_interval / interval))
            if self._screenshot_counter >= polls_needed:
                self._screenshot_counter = 0
                img = await self.client.screenshot()
                if img:
                    self.screenshot_data = img

        return data
