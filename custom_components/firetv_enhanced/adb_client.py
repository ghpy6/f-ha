"""Lightweight ADB client for Fire TV."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from adb_shell.adb_device_async import AdbDeviceTcpAsync
from adb_shell.auth.keygen import keygen
from adb_shell.auth.sign_pythonrsa import PythonRSASigner

_LOGGER = logging.getLogger(__name__)

_RE_RESUMED = re.compile(r"mResumedActivity.*?(\S+)/")
_RE_CURRENT_APP = re.compile(r"[{/]\s*(com\.\S+|org\.\S+|tv\.\S+|net\.\S+)")


def _setup_key_sync(config_dir: str | None) -> PythonRSASigner:
    """Generate/load ADB key. BLOCKING — must be called from executor only."""
    if config_dir:
        key_dir = os.path.join(config_dir, ".firetv_enhanced")
    else:
        key_dir = os.path.join(os.path.expanduser("~"), ".firetv_enhanced")
    os.makedirs(key_dir, exist_ok=True)
    key_path = os.path.join(key_dir, "adbkey")

    if not os.path.exists(key_path):
        _LOGGER.info("Generating new ADB key at %s", key_path)
        keygen(key_path)

    with open(key_path) as f:
        priv = f.read()

    pub = ""
    pub_path = key_path + ".pub"
    if os.path.exists(pub_path):
        with open(pub_path) as f:
            pub = f.read()

    return PythonRSASigner(pub, priv)


class FireTVClient:
    """Async ADB client optimized for Fire TV."""

    def __init__(
        self, host: str, port: int = 5555, hass_config_dir: str | None = None
    ) -> None:
        self.host = host
        self.port = port
        self._hass_config_dir = hass_config_dir
        self._device: AdbDeviceTcpAsync | None = None
        self._lock = asyncio.Lock()
        self._signer: PythonRSASigner | None = None

    @property
    def connected(self) -> bool:
        return self._device is not None and self._device.available

    async def connect(self, timeout: float = 30.0) -> bool:
        """Connect to Fire TV. 30s timeout to allow TV approval dialog."""
        try:
            # Load/create key in executor (not in event loop)
            if self._signer is None:
                loop = asyncio.get_running_loop()
                self._signer = await loop.run_in_executor(
                    None, _setup_key_sync, self._hass_config_dir
                )

            self._device = AdbDeviceTcpAsync(
                self.host, self.port, default_transport_timeout_s=timeout
            )

            await self._device.connect(
                rsa_keys=[self._signer],
                auth_timeout_s=timeout,
            )

            _LOGGER.info("Connected to Fire TV at %s:%d", self.host, self.port)
            return True

        except Exception as err:
            _LOGGER.error(
                "Failed to connect to Fire TV at %s:%d — %s: %s",
                self.host, self.port, type(err).__name__, err,
            )
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
        """Get device state in ONE ADB call."""
        result = await self._shell(
            "dumpsys power | grep -E 'Display Power|mWakefulness' ; "
            "dumpsys activity activities | grep mResumedActivity ; "
            "dumpsys window | grep -E mCurrentFocus"
        )
        if not result:
            return {"screen_on": False, "app_package": None}

        screen_on = "Display Power: state=ON" in result or "Awake" in result

        app_package = None
        match = _RE_RESUMED.search(result)
        if match:
            app_package = match.group(1)
        else:
            match = _RE_CURRENT_APP.search(result)
            if match:
                app_package = match.group(1).split("/")[0]

        return {"screen_on": screen_on, "app_package": app_package}

    async def screenshot(self) -> bytes | None:
        """Take screenshot. Returns PNG bytes at native 16:9 resolution."""
        return await self._shell("exec-out screencap -p", binary=True)

    async def send_key(self, key: str) -> None:
        await self._shell(f"input keyevent {key}")

    async def launch_app(self, package: str) -> None:
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
