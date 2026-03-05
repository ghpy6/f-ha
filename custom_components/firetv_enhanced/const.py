"""Constants for Fire TV Enhanced."""

DOMAIN = "firetv_enhanced"
DEFAULT_PORT = 5555
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_SCREENSHOT_INTERVAL = 10

# Package → friendly name + icon.
# Note on Amazon packages:
#   com.amazon.avod = Prime Video (the main app)
#   com.amazon.firebat = Silk Browser (Amazon's web browser)
#   com.amazon.venezia = Amazon App Store (not Amazon Music!)
#   com.amazon.cloud9 = Silk Browser (older package name)
#   com.amazon.music.tv = Amazon Music
#   com.amazon.hedwig = Alexa voice service
#   com.amazon.cardinal = App Manager (system)
APP_MAP: dict[str, dict[str, str]] = {
    "com.netflix.ninja": {"name": "Netflix", "icon": "mdi:netflix"},
    "com.google.android.youtube.tv": {"name": "YouTube", "icon": "mdi:youtube"},
    "com.amazon.avod": {"name": "Prime Video", "icon": "mdi:amazon"},
    "com.amazon.tv.launcher": {"name": "Home", "icon": "mdi:home"},
    "com.disney.disneyplus": {"name": "Disney+", "icon": "mdi:filmstrip"},
    "com.globo.globotv": {"name": "Globoplay", "icon": "mdi:television-play"},
    "com.spotify.tv.android": {"name": "Spotify", "icon": "mdi:spotify"},
    "com.apple.atv": {"name": "Apple TV", "icon": "mdi:apple"},
    "com.apple.android.music": {"name": "Apple Music", "icon": "mdi:apple"},
    "com.amazon.hedwig": {"name": "Alexa", "icon": "mdi:microphone"},
    "com.amazon.firetv.youtube": {"name": "YouTube (Fire)", "icon": "mdi:youtube"},
    "org.xbmc.kodi": {"name": "Kodi", "icon": "mdi:kodi"},
    "com.plexapp.android": {"name": "Plex", "icon": "mdi:plex"},
    "tv.twitch.android.app": {"name": "Twitch", "icon": "mdi:twitch"},
    "tv.twitch.android.viewer": {"name": "Twitch", "icon": "mdi:twitch"},
    "com.hbo.hbonow": {"name": "HBO Max", "icon": "mdi:filmstrip"},
    "com.crunchyroll.crunchyroid": {"name": "Crunchyroll", "icon": "mdi:animation-play"},
    "com.amazon.venezia": {"name": "App Store", "icon": "mdi:store"},
    "com.amazon.tv.settings": {"name": "Settings", "icon": "mdi:cog"},
    "com.amazon.firetv.screensaver": {"name": "Screensaver", "icon": "mdi:weather-night"},
    "com.amazon.tv.notificationcenter": {"name": "Notifications", "icon": "mdi:bell"},
    "com.amazon.music.tv": {"name": "Amazon Music", "icon": "mdi:music"},
    "com.amazon.firebat": {"name": "Silk Browser", "icon": "mdi:web"},
    "com.amazon.cloud9": {"name": "Silk Browser", "icon": "mdi:web"},
    "com.amazon.cardinal": {"name": "App Manager", "icon": "mdi:apps"},
    "com.deezer.tv": {"name": "Deezer", "icon": "mdi:music"},
    "com.bamtechmedia.dominguez.main": {"name": "Star+", "icon": "mdi:star"},
    "com.liskovsoft.smarttubetv.beta": {"name": "SmartTube", "icon": "mdi:youtube-tv"},
    "com.liskovsoft.smarttubetv": {"name": "SmartTube", "icon": "mdi:youtube-tv"},
}
