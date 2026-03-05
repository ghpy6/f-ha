# Fire TV Enhanced

A custom Home Assistant integration for Fire TV devices. Communicates directly with your Fire TV over ADB (Android Debug Bridge) on your local network. No cloud, no extra apps, no dependencies beyond what Home Assistant already includes.

## What it does

- Detects which app is running on your Fire TV in real time
- Takes live screenshots of the Fire TV screen (16:9, displayed on your dashboard)
- Play, pause, stop, skip, previous track controls
- Turn Fire TV on and off
- Launch any installed app from your dashboard or automations
- Auto-discovers all third-party apps installed on your device
- Custom app name mapping (rename any app to whatever you want)
- Send notifications to the Fire TV screen (experimental)

## Requirements

- Home Assistant 2025.1.0 or newer
- Fire TV Stick or Fire TV device with ADB Debugging enabled
- Both devices on the same Wi-Fi network

## Installation

### Step 1: Enable ADB on your Fire TV

1. Open Settings on your Fire TV
2. Go to My Fire TV
3. Go to Developer Options
4. Turn on ADB Debugging

If you don't see Developer Options, go to My Fire TV, About, and click on your device name 7 times to unlock it.

### Step 2: Find your Fire TV IP address

1. Open Settings on your Fire TV
2. Go to My Fire TV
3. Go to About
4. Go to Network
5. Note the IP Address shown

### Step 3: Install via HACS

1. Open HACS in Home Assistant
2. Click the three-dot menu in the top right
3. Click Custom repositories
4. Paste your repository URL
5. Select Integration as the category
6. Click Add
7. Search for Fire TV Enhanced and click Download
8. Restart Home Assistant

### Step 4: Add the integration

1. Go to Settings, Devices and Services
2. Click Add Integration
3. Search for Fire TV Enhanced
4. Enter your Fire TV IP address
5. Click Submit
6. A prompt will appear on your TV screen. Check "Always allow from this computer" and select Allow with your remote. You have 30 seconds.

## Entities created

**Media Player** (media_player.fire_tv): Main control entity. Shows current app, playback state. Supports play, pause, stop, skip, power, and source selection (app launching).

**Current App** (sensor.fire_tv_current_app): Friendly name of the currently running app.

**App Package** (sensor.fire_tv_app_package): Raw Android package name of the running app. Use this to find package names for custom app name mapping or launch commands.

**Screen** (camera.fire_tv_screen): Live screenshot of the Fire TV display. Updates at the configured screenshot interval.

## Dashboard setup

Basic setup with live screenshot and media controls:

```yaml
type: grid
cards:
  - type: picture-entity
    entity: camera.fire_tv_screen
    show_state: false
    show_name: false
    camera_view: live
    aspect_ratio: "16:9"
  - type: media-control
    entity: media_player.fire_tv
```

App launch buttons using the launch_app service:

```yaml
type: button
name: Netflix
icon: mdi:netflix
tap_action:
  action: perform-action
  perform_action: firetv_enhanced.launch_app
  data:
    package: com.netflix.ninja
```

Common package names (find yours using the App Package sensor):

| App | Package |
|-----|---------|
| Netflix | com.netflix.ninja |
| YouTube | com.google.android.youtube.tv |
| Prime Video | com.amazon.avod |
| Disney+ | com.disney.disneyplus |
| Spotify | com.spotify.tv.android |
| Apple TV | com.apple.atv |
| Plex | com.plexapp.android |
| Kodi | org.xbmc.kodi |
| SmartTube | com.liskovsoft.smarttubetv.beta |
| Amazon Music | com.amazon.music.tv |
| Silk Browser | com.amazon.cloud9 |

Note: Some Amazon system packages have confusing names. `com.amazon.firebat` is Silk Browser, not Prime Video. `com.amazon.venezia` is the App Store, not Amazon Music. Always check the App Package sensor to confirm.

## Configuration

After installation, click Configure (gear icon) on the integration to adjust:

**App detection interval**: How often to check which app is running. Default 5 seconds. Can go as low as 1 second.

**Screenshot interval**: How often to capture a screenshot. Default 10 seconds. Can go as low as 1 second. Lower values use more network bandwidth.

**Custom app names**: Rename apps that show with auto-generated names. One entry per line:

```
com.apple.atv = Apple TV
tv.twitch.android.viewer = Twitch
com.liskovsoft.smarttubetv.beta = SmartTube
```

Use the App Package sensor to find the exact package name for any app. Open the app on your Fire TV, then check the sensor value.

## Services

Available under Developer Tools, Actions tab.

**firetv_enhanced.launch_app**: Launch an app by package name.

```yaml
action: firetv_enhanced.launch_app
data:
  package: com.netflix.ninja
```

**firetv_enhanced.send_notification**: Show a notification on the Fire TV screen. This is experimental and may not work on all Fire TV OS versions.

```yaml
action: firetv_enhanced.send_notification
data:
  title: Home Assistant
  message: Dinner is ready
```

## How it works

Fire TV runs a modified version of Android called Fire OS. Like all Android devices, it includes ADB (Android Debug Bridge), a built-in protocol for communicating with the device over a network connection.

This integration uses the `adb-shell` Python library (already included in Home Assistant) to open a TCP connection to port 5555 on your Fire TV. Every feature is an ADB shell command:

- App detection: `dumpsys activity` to check which app is in the foreground
- Screenshot: `screencap -p | base64` to capture the screen (base64 encoded to avoid binary corruption over ADB)
- Media controls: `input keyevent` with numeric keycodes (126=play, 127=pause, etc.)
- App launching: `monkey -p <package> -c android.intent.category.LAUNCHER 1`
- App discovery: `pm list packages -3` to list all installed third-party apps

The ADB connection is authenticated with an RSA key pair stored at `/config/.firetv_enhanced/adbkey`. Once your Fire TV trusts this key (the "Always allow" checkbox during setup), reconnections are automatic.

## Known limitations

**Volume control**: Not possible via ADB on Fire TV Stick. The physical remote controls your TV volume via an IR blaster built into the remote hardware. This signal goes directly from the remote to the TV, never through the Fire TV software.

**TV power control**: Same limitation. The remote's power button uses IR, not HDMI-CEC through software. Turning off the Fire TV via ADB puts the Fire TV to sleep but does not turn off your TV.

**DRM screenshots**: Apps like Netflix and Disney+ use DRM protection. Screenshots from these apps will appear black. This is an Android security feature.

**Notification delivery**: The send_notification service uses Android system commands that may not be available on all Fire TV OS versions. Some Fire TV models disable the notification subsystem entirely.

## Troubleshooting

**Cannot connect**: Verify ADB Debugging is enabled. Check that the IP address is correct. Make sure both devices are on the same network. Try restarting the Fire TV.

**TV prompt not appearing**: The Fire TV may have already denied the key. Go to Fire TV Settings, My Fire TV, Developer Options, and look for an option to revoke USB debugging authorizations. Revoke them, then try adding the integration again.

**App names showing as package names**: Open the app, check the App Package sensor for the exact package name, then add a custom name mapping in the integration settings.

**Screenshots not loading**: If screenshots appear corrupted or don't load, check the Home Assistant logs for errors from the `firetv_enhanced` component. The base64 encoding method should work on all Fire TV models, but some very old firmware versions may have issues.

**Services not visible**: Go to Developer Tools, then click the Actions tab (not YAML). Search for "firetv_enhanced". If nothing appears, restart Home Assistant after installing the integration.
