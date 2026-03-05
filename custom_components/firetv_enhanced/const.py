"""Constants for Fire TV Enhanced."""

DOMAIN = "firetv_enhanced"
DEFAULT_PORT = 5555
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_SCREENSHOT_INTERVAL = 10

# ONLY system packages needed for state detection logic.
# All user apps come from auto-discovery (pm list packages -3)
# and user custom names in the options flow. Nothing is pre-added.
SYSTEM_APPS: dict[str, dict[str, str]] = {
    "com.amazon.tv.launcher": {"name": "Home", "icon": "mdi:home"},
    "com.amazon.firetv.screensaver": {"name": "Screensaver", "icon": "mdi:weather-night"},
    "com.amazon.tv.settings": {"name": "Settings", "icon": "mdi:cog"},
    "com.amazon.tv.notificationcenter": {"name": "Notifications", "icon": "mdi:bell"},
}

# Packages to hide from the source/launch list
SKIP_SOURCES = {
    "com.amazon.tv.launcher",
    "com.amazon.firetv.screensaver",
    "com.amazon.tv.settings",
    "com.amazon.tv.notificationcenter",
}
