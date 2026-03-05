"""Data coordinator for Fire TV Enhanced."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adb_client import FireTVClient
from .const import SYSTEM_APPS, SKIP_SOURCES, DEFAULT_SCAN_INTERVAL, DEFAULT_SCREENSHOT_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FireTVCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, client: FireTVClient, name: str,
                 scan_interval: int = DEFAULT_SCAN_INTERVAL,
                 screenshot_interval: int = DEFAULT_SCREENSHOT_INTERVAL) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{name}",
                        update_interval=timedelta(seconds=scan_interval))
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

    def _auto_name(self, package: str) -> str:
        """Generate a readable name from a package string."""
        parts = package.split(".")
        if len(parts) >= 2:
            raw = parts[-1]
            # Handle common patterns
            raw = raw.replace("_", " ").replace("-", " ")
            return raw.title()
        return package

    def get_app_name(self, package: str | None) -> str:
        if not package:
            return "Off"
        # 1. User custom names first
        if package in self._custom_apps:
            return self._custom_apps[package]
        # 2. System apps (for state detection display)
        if package in SYSTEM_APPS:
            return SYSTEM_APPS[package]["name"]
        # 3. Auto-generate from package name
        return self._auto_name(package)

    def get_app_icon(self, package: str | None) -> str:
        if not package:
            return "mdi:television-off"
        if package in SYSTEM_APPS:
            return SYSTEM_APPS[package]["icon"]
        return "mdi:application"

    def get_source_list(self) -> list[str]:
        """Launchable apps: discovered + custom, excluding system."""
        names = set()
        for pkg in self._discovered_packages:
            if pkg not in SKIP_SOURCES:
                names.add(self.get_app_name(pkg))
        for pkg, name in self._custom_apps.items():
            if pkg not in SKIP_SOURCES:
                names.add(name)
        return sorted(names)

    def get_package_for_source(self, source: str) -> str | None:
        # Check custom first
        for pkg, name in self._custom_apps.items():
            if name == source:
                return pkg
        # Check discovered
        for pkg in self._discovered_packages:
            if self.get_app_name(pkg) == source:
                return pkg
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        if not self.client.connected:
            if not await self.client.connect():
                raise UpdateFailed("Cannot connect to Fire TV")

        if not self._discovery_done:
            try:
                self._discovered_packages = await self.client.discover_apps()
                self._discovery_done = True
                _LOGGER.info("Discovered %d apps on Fire TV", len(self._discovered_packages))
            except Exception:
                pass

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

        if screen_on and package not in SKIP_SOURCES and package is not None:
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
