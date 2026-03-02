"""Lightweight ADB client for Fire TV."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

_LOGGER = logging.getLogger(__name__)

# Regex to extract package from mCurrentFocus or mResumedActivity
_RE_CURRENT_APP = re.compile(r"[{/]\s*(com\.\S+|org\.\S+|tv\.\S+|net\.\S+)")
_RE_RESUMED = re.compile(r"mResumedActivity.*?(\S+)/")
_RE_VOLUME = re.compile(r"STREAM_MUSIC.*?index[=:](\d+)", re.DOTALL)
_RE_MUTED = re.compile(r"STREAM_MUSIC.*?mute.*?(true|false)", re.DOTALL | re.IGNORECASE)


class FireTVClient:
    """Async ADB client optimized for Fire TV."""

    def __init__(self, host: str, port: int = 5555, adb_key_path: str | None = None) -> None:
        self.host = host
        self.port = port
        self._adb_key_path = adb_key_path
        self._device: AdbDeviceTcpAsync | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._device is not None and self._device.available

    async def connect(self) -> bool:
        """Connect to the Fire TV device."""
        try:
            self._device = AdbDeviceTcpAsync(self.host, self.port)
            signer = None

            if self._adb_key_path:
                with open(self._adb_key_path) as f:
                    priv = f.read()
                signer = PythonRSASigner("", priv)
            else:
                # Generate a key if none provided
                import tempfile, os
                key_path = os.path.join(tempfile.gettempdir(), "firetv_enhanced_adbkey")
                if not os.path.exists(key_path):
                    keygen(key_path)
                with open(key_path) as f:
                    priv = f.read()
                signer = PythonRSASigner("", priv)

            await self._device.connect(rsa_keys=[signer], auth_timeout_s=10.0)
            _LOGGER.info("Connected to Fire TV at %s:%d", self.host, self.port)
            return True

        except Exception as err:
            _LOGGER.error("Failed to connect to %s:%d: %s", self.host, self.port, err)
            self._device = None
            return False

    async def disconnect(self) -> None:
        if self._device:
            await self._device.close()
            self._device = None

    async def _shell(self, cmd: str, binary: bool = False) -> Any:
        """Execute ADB shell command."""
        if not self.connected:
            return None
        try:
            async with self._lock:
                if binary:
                    return await self._device.shell(cmd, decode=False)
                return await self._device.shell(cmd)
        except Exception as err:
            _LOGGER.debug("ADB command failed: %s — %s", cmd, err)
            return None

    async def get_state(self) -> dict[str, Any]:
        """Get full device state in ONE ADB call. ~100ms."""
        result = await self._shell(
            "dumpsys power | grep -E 'Display Power|mWakefulness' ; "
            "dumpsys activity activities | grep mResumedActivity ; "
            "dumpsys window | grep -E mCurrentFocus"
        )
        if not result:
            return {"screen_on": False, "app_package": None}

        screen_on = "Display Power: state=ON" in result or "Awake" in result

        # Try mResumedActivity first (more reliable)
        app_package = None
        match = _RE_RESUMED.search(result)
        if match:
            app_package = match.group(1)
        else:
            # Fallback to mCurrentFocus
            match = _RE_CURRENT_APP.search(result)
            if match:
                pkg = match.group(1)
                # Clean up: remove activity name after /
                app_package = pkg.split("/")[0]

        return {"screen_on": screen_on, "app_package": app_package}

    async def get_volume_info(self) -> dict[str, Any]:
        """Get volume level and mute state."""
        result = await self._shell(
            "dumpsys audio | grep -A5 STREAM_MUSIC"
        )
        if not result:
            return {"volume": 0, "muted": False}

        volume = 0
        muted = False
        m = _RE_VOLUME.search(result)
        if m:
            volume = int(m.group(1))
        m = _RE_MUTED.search(result)
        if m:
            muted = m.group(1).lower() == "true"
        return {"volume": volume, "muted": muted}

    async def screenshot(self) -> bytes | None:
        """Take a screenshot. Returns PNG bytes at native resolution (16:9)."""
        return await self._shell("exec-out screencap -p", binary=True)

    async def send_key(self, key: str) -> None:
        """Send a key event (HOME, BACK, MEDIA_PLAY_PAUSE, etc.)."""
        await self._shell(f"input keyevent {key}")

    async def launch_app(self, package: str) -> None:
        """Launch an app by package name."""
        await self._shell(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )

    async def turn_on(self) -> None:
        await self._shell("input keyevent WAKEUP")

    async def turn_off(self) -> None:
        await self._shell("input keyevent SLEEP")

    async def volume_up(self) -> None:
        await self._shell("input keyevent VOLUME_UP")

    async def volume_down(self) -> None:
        await self._shell("input keyevent VOLUME_DOWN")

    async def volume_mute(self) -> None:
        await self._shell("input keyevent VOLUME_MUTE")

    async def media_play_pause(self) -> None:
        await self._shell("input keyevent MEDIA_PLAY_PAUSE")

    async def media_stop(self) -> None:
        await self._shell("input keyevent MEDIA_STOP")

    async def media_next(self) -> None:
        await self._shell("input keyevent MEDIA_NEXT")

    async def media_previous(self) -> None:
        await self._shell("input keyevent MEDIA_PREVIOUS")

    async def navigate_back(self) -> None:
        await self._shell("input keyevent BACK")

    async def navigate_home(self) -> None:
        await self._shell("input keyevent HOME")
