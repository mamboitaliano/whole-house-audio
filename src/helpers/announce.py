# src/helpers/announce.py
import subprocess, time, os, yaml
from .. import iscp

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "zones.yaml")

def load_zones():
    try:
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
        return data.get("zones", {})
    except Exception as e:
        print(f"[announce] zones load error: {e}")
        return {}

def _hex_from_percent(p): p = max(0, min(100, int(p))); return f"{p:02X}"
def _mpc(*args): return subprocess.run(["mpc", *args], check=False)

def _mpc_status_text():
    p = subprocess.Popen(["mpc", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, _ = p.communicate()
    return out or ""

def _wait_mpc_stop(max_s=60):
    end = time.time() + max_s
    while time.time() < end:
        if "[playing]" not in _mpc_status_text():
            return
        time.sleep(0.2)

def play_zone_announcement(zone_name: str, volume_pct: int, file_url: str):
    zones = load_zones()
    if zone_name not in zones:
        raise ValueError(f"unknown zone '{zone_name}'")
    cfg = zones[zone_name] or {}
    zone_id = str(cfg.get("zone_id", "1"))
    ann_sli = str(cfg.get("sli", "2B")).upper()

    # single-receiver deployment: IP from env or hardcoded in systemd
    ip = os.environ.get("DEFAULT_RECEIVER_IP", "192.168.50.249")
    cli = iscp.EISCPClient(ip)

    # Ensure power for this zone
    cli.power(True, zone=zone_id); time.sleep(0.1)

    # Snapshot this zone's input & volume
    prev_in  = cli.input_query(zone_id) or ""
    prev_v   = cli.volume_query(zone_id) or ""
    prev_hex = prev_v[-2:] if len(prev_v) >= 2 else "32"
    was_on_ann_input = prev_in.endswith(ann_sli)

    # Switch only this zone to the announcement input and set volume
    cli.input_select(ann_sli, zone=zone_id); time.sleep(0.08)
    cli.volume_hex(_hex_from_percent(volume_pct), zone=zone_id); time.sleep(0.05)

    muted = False
    if was_on_ann_input:
        cli.mute(True, zone=zone_id); muted = True; time.sleep(0.05)

    # Play the URL (Pi/MPD is the shared source)
    _mpc("clear"); _mpc("add", file_url); _mpc("play")
    _wait_mpc_stop(max_s=120)

    if muted:
        cli.mute(False, zone=zone_id); time.sleep(0.05)

    # Restore this zone's previous input & volume
    prev_sli = prev_in[-2:].upper() if len(prev_in) >= 2 else None
    if prev_sli and all(c in "0123456789ABCDEF" for c in prev_sli):
        cli.input_select(prev_sli, zone=zone_id); time.sleep(0.05)
    if prev_hex and all(c in "0123456789ABCDEF" for c in prev_hex.upper()):
        cli.volume_hex(prev_hex.upper(), zone=zone_id)
