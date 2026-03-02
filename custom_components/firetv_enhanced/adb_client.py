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
            # This prevents the 30s delay on the first real command
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

        # Playback state (playing, paused, stopped, etc.)
        match = _RE_MEDIA_STATE.search(result)
        if match:
            state_num = int(match.group(1))
            info["playback_state"] = PLAYBACK_STATES.get(state_num, "unknown")

        # Media title
        match = _RE_MEDIA_TITLE.search(result)
        if match:
            title = match.group(1).strip()
            if title and title != "null":
                info["media_title"] = title

        return info

    async def screenshot(self) -> bytes | None:
        """Take screenshot. Returns PNG bytes at native resolution."""
        data = await self._shell_bytes("screencap -p")
        if not data or len(data) < 100:
            return None

        # ADB sometimes corrupts binary by replacing \n with \r\n
        # Fix: replace \r\n back to \n only in non-PNG-header areas
        # Check PNG signature
        if data[:4] == b'\x89PNG':
            return data

        # If corrupted, try the \r\n fix
        fixed = data.replace(b'\r\n', b'\n')
        if fixed[:4] == b'\x89PNG':
            return fixed

        # Still broken — try alternative method
        _LOGGER.debug("Screenshot PNG repair failed, trying alternative")
        return None

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

    async def set_volume(self, level: int) -> None:
        """Set volume directly using media command."""
        await self._shell(f"media volume --set {level} --stream 3")

    async def volume_up(self) -> None:
        await self._shell("media volume --adj raise --stream 3")

    async def volume_down(self) -> None:
        await self._shell("media volume --adj lower --stream 3")

    async def volume_mute(self) -> None:
        await self._shell("media volume --adj mute --stream 3")

    async def get_volume(self) -> dict[str, Any]:
        """Get current volume level."""
        result = await self._shell("media volume --get --stream 3")
        volume = 50
        muted = False
        if result:
            # Parse: "Volume is X in range [0..Y]"
            import re as _re
            m = _re.search(r"Volume is (\d+) in range \[0\.\.(\d+)\]", result)
            if m:
                vol = int(m.group(1))
                max_vol = int(m.group(2))
                volume = round((vol / max_vol) * 100) if max_vol > 0 else 0
            muted = "is muted" in result.lower()
        return {"volume": volume, "muted": muted}

    async def media_play_pause(self) -> None:
        await self._shell("input keyevent MEDIA_PLAY_PAUSE")

    async def media_play(self) -> None:
        await self._shell("input keyevent MEDIA_PLAY")

    async def media_pause(self) -> None:
        await self._shell("input keyevent MEDIA_PAUSE")

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
