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
_RE_MEDIA_STATE = re.compile(r"state=PlaybackState\{state=(\d+)")
_RE_MEDIA_TITLE = re.compile(r"description=.*?title=(.*?)(?:,|$)", re.DOTALL)

# Android keycodes (numeric = always works, string names can fail on Fire TV)
_KEY_POWER = 26
_KEY_WAKEUP = 224
_KEY_SLEEP = 223
_KEY_PLAY = 126
_KEY_PAUSE = 127
_KEY_PLAY_PAUSE = 85
_KEY_STOP = 86
_KEY_NEXT = 87
_KEY_PREVIOUS = 88
_KEY_VOLUME_UP = 24
_KEY_VOLUME_DOWN = 25
_KEY_MUTE = 164
_KEY_BACK = 4
_KEY_HOME = 3

# Android PlaybackState constants
PLAYBACK_STATES = {
    0: "none",
    1: "stopped",
    2: "paused",
    3: "playing",
    4: "fast_forwarding",
    5: "rewinding",
    6: "buffering",
    7: "error",
    8: "connecting",
    9: "skipping_previous",
    10: "skipping_next",
}


def _setup_key_sync(config_dir: str | None) -> PythonRSASigner:
    """Generate/load ADB key. BLOCKING — runs in executor only."""
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

            # Warm up: run a quick command to fully establish the session
            # This prevents delay on the first real command
            await self._device.shell("echo ok")

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

    async def _shell(self, cmd: str) -> str | None:
        """Execute ADB shell command, return text."""
        if not self.connected:
            return None
        try:
            async with self._lock:
                return await self._device.shell(cmd)
        except Exception as err:
            _LOGGER.debug("ADB command failed: %s — %s", cmd, err)
            return None

    async def _shell_bytes(self, cmd: str) -> bytes | None:
        """Execute ADB shell command, return raw bytes."""
        if not self.connected:
            return None
        try:
            async with self._lock:
                return await self._device.shell(cmd, decode=False)
        except Exception as err:
            _LOGGER.debug("ADB binary command failed: %s — %s", cmd, err)
            return None

    async def _key(self, keycode: int) -> None:
        """Send a keyevent by numeric code (always reliable)."""
        await self._shell(f"input keyevent {keycode}")

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

    async def get_media_info(self) -> dict[str, Any]:
        """Get media session info (what's playing, state, title)."""
        result = await self._shell(
            "dumpsys media_session | grep -A 20 'state=PlaybackState'"
        )
        info: dict[str, Any] = {
            "playback_state": "idle",
            "media_title": None,
        }
        if not result:
            return info

        match = _RE_MEDIA_STATE.search(result)
        if match:
            state_num = int(match.group(1))
            info["playback_state"] = PLAYBACK_STATES.get(state_num, "unknown")

        match = _RE_MEDIA_TITLE.search(result)
        if match:
            title = match.group(1).strip()
            if title and title != "null":
                info["media_title"] = title

        return info

    async def screenshot(self) -> bytes | None:
        """Take screenshot. Returns PNG bytes at native 16:9 resolution.

        Uses exec-out for raw binary stream (prevents \\r\\n corruption).
        """
        data = await self._shell_bytes("exec-out screencap -p")
        if not data or len(data) < 100:
            _LOGGER.debug("Screenshot returned no/tiny data (%d bytes)",
                         len(data) if data else 0)
            return None

        # Verify PNG signature
        if data[:4] == b'\x89PNG':
            return data

        # Fallback: fix \r\n corruption (shouldn't happen with exec-out)
        fixed = data.replace(b'\r\n', b'\n')
        if fixed[:4] == b'\x89PNG':
            _LOGGER.debug("Screenshot needed \\r\\n repair")
            return fixed

        _LOGGER.warning("Screenshot is not valid PNG (%d bytes, header: %s)",
                       len(data), data[:8].hex())
        return None

    # --- Media controls (numeric keycodes) ---

    async def media_play(self) -> None:
        await self._key(_KEY_PLAY)

    async def media_pause(self) -> None:
        await self._key(_KEY_PAUSE)

    async def media_play_pause(self) -> None:
        await self._key(_KEY_PLAY_PAUSE)

    async def media_stop(self) -> None:
        await self._key(_KEY_STOP)

    async def media_next(self) -> None:
        await self._key(_KEY_NEXT)

    async def media_previous(self) -> None:
        await self._key(_KEY_PREVIOUS)

    # --- Volume (keycodes go through HDMI-CEC to control TV volume) ---

    async def volume_up(self) -> None:
        await self._key(_KEY_VOLUME_UP)

    async def volume_down(self) -> None:
        await self._key(_KEY_VOLUME_DOWN)

    async def volume_mute(self) -> None:
        await self._key(_KEY_MUTE)

    # --- Navigation ---

    async def turn_on(self) -> None:
        await self._key(_KEY_WAKEUP)

    async def turn_off(self) -> None:
        await self._key(_KEY_SLEEP)

    async def navigate_back(self) -> None:
        await self._key(_KEY_BACK)

    async def navigate_home(self) -> None:
        await self._key(_KEY_HOME)

    async def launch_app(self, package: str) -> None:
        await self._shell(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
