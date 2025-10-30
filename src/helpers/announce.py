import subprocess
import time
import yaml
import os

from .. import mpd_control, iscp


# Path to the zone configuration file
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "config", "zones.yaml"
)


def load_zones():
    """Load zone map from YAML file."""
    try:
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f)
        return data.get("zones", {})
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[announce] Error loading config: {e}")
        return {}


def play_announcement(url, volume=None, zone=None, resume=True):
    """
    Play a temporary announcement.

    Args:
        url (str): The audio URL or file path.
        volume (int, optional): Volume (0–100).
        zone (str, optional): Named zone to temporarily switch to.
        resume (bool): Whether to resume playback afterward.
    """

    zones = load_zones()
    target_zone = zones.get(zone) if zone else None

    # Capture current state
    status = mpd_control.get_status()
    was_playing = status.get("state") == "play"
    current_song = status.get("file")

    print(f"[announce] Starting announcement: url={url}, zone={zone}, resume={resume}")

    # Optional: handle zone switching
    prev_zone = None
    if target_zone:
        prev_zone = _detect_active_zone(zones)
        _switch_zone(target_zone)

    # Pause current music
    if was_playing:
        mpd_control.pause()

    # Adjust volume if requested
    if volume is not None:
        subprocess.run(["mpc", "volume", str(volume)], check=False)

    # Play the announcement
    subprocess.run(["mpc", "clear"], check=False)
    subprocess.run(["mpc", "add", url], check=False)
    subprocess.run(["mpc", "play"], check=False)

    # Wait for playback to end
    _wait_for_stop()

    # Resume previous song if needed
    if resume and was_playing and current_song:
        print("[announce] Resuming previous playback")
        subprocess.run(["mpc", "clear"], check=False)
        subprocess.run(["mpc", "add", current_song], check=False)
        subprocess.run(["mpc", "play"], check=False)

    # Switch back to previous zone if changed
    if target_zone and prev_zone:
        _switch_zone(prev_zone)

    print("[announce] Done.")


# --- Internal helpers ---------------------------------------------------------


def _wait_for_stop():
    """Block until MPD playback stops."""
    while True:
        st = mpd_control.get_status()
        if st.get("state") != "play":
            break
        time.sleep(1)


def _detect_active_zone(zones):
    """(Future enhancement) Detect which receiver is currently active."""
    # For now, just return the first zone (you could ping receivers or query state)
    return next(iter(zones.values()), None)


def _switch_zone(zone_cfg):
    """Send ISCP command to switch receiver input."""
    ip = zone_cfg.get("receiver_ip")
    input_src = zone_cfg.get("input", "net")

    if not ip:
        print("[announce] No receiver_ip in zone config, skipping zone switch")
        return

    print(f"[announce] Switching receiver {ip} to input '{input_src}'")
    cmd = _iscp_input_command(input_src)
    rc, out, err = iscp.send_iscp(ip, cmd)
    if rc != 0:
        print(f"[announce] ISCP switch failed: {err}")


def _iscp_input_command(source):
    """Return ISCP command string for a given source name."""
    mapping = {
        "net": "!1SLI2B\r",
        "bd": "!1SLI10\r",
        "tv": "!1SLI00\r",
        "game": "!1SLI02\r",
        "pc": "!1SLI05\r",
        "aux": "!1SLI03\r",
    }
    return mapping.get(source.lower(), "!1SLI2B\r")
