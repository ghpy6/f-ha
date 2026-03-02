"""Constants for Fire TV Enhanced."""

DOMAIN = "firetv_enhanced"
DEFAULT_PORT = 5555
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_SCREENSHOT_INTERVAL = 10

CONF_ADB_KEY = "adb_key"

# Package name → friendly name + icon
APP_MAP: dict[str, dict[str, str]] = {
    "com.netflix.ninja": {"name": "Netflix", "icon": "mdi:netflix"},
    "com.google.android.youtube.tv": {"name": "YouTube", "icon": "mdi:youtube"},
    "com.amazon.avod": {"name": "Prime Video", "icon": "mdi:amazon"},
    "com.amazon.tv.launcher": {"name": "Home", "icon": "mdi:home"},
    "com.disney.disneyplus": {"name": "Disney+", "icon": "mdi:filmstrip"},
    "com.globo.globotv": {"name": "Globoplay", "icon": "mdi:television-play"},
    "com.spotify.tv.android": {"name": "Spotify", "icon": "mdi:spotify"},
    "com.amazon.hedwig": {"name": "Alexa", "icon": "mdi:microphone"},
    "com.amazon.firetv.youtube": {"name": "YouTube", "icon": "mdi:youtube"},
    "org.xbmc.kodi": {"name": "Kodi", "icon": "mdi:kodi"},
    "com.plexapp.android": {"name": "Plex", "icon": "mdi:plex"},
    "tv.twitch.android.app": {"name": "Twitch", "icon": "mdi:twitch"},
    "com.hbo.hbonow": {"name": "HBO Max", "icon": "mdi:filmstrip"},
    "com.crunchyroll.crunchyroid": {"name": "Crunchyroll", "icon": "mdi:animation-play"},
    "com.amazon.venezia": {"name": "App Store", "icon": "mdi:store"},
    "com.amazon.tv.settings": {"name": "Settings", "icon": "mdi:cog"},
    "com.amazon.firetv.screensaver": {"name": "Screensaver", "icon": "mdi:weather-night"},
    "com.amazon.tv.notificationcenter": {"name": "Notifications", "icon": "mdi:bell"},
}
