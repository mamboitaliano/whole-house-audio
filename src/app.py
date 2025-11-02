# Flask routes only

from flask import Flask, jsonify, request
import os
import re
import socket

from . import mpd_control, playback, iscp
from . import deploy
from .helpers import announce  # already imported once; no need to import inside routes

app = Flask(__name__)

# ---- Config / helpers ---------------------------------------------------------

DEFAULT_RECEIVER_IP = os.environ.get("DEFAULT_RECEIVER_IP", "192.168.50.249")

def get_receiver_ip() -> str:
    # Single source of truth; easy to override later if needed
    return DEFAULT_RECEIVER_IP

def get_client() -> iscp.EISCPClient:
    return iscp.EISCPClient(get_receiver_ip())

INPUT_CODE_MAP = {
    "00": "TV",
    "02": "GAME",
    "03": "AUX",
    "05": "PC",
    "10": "BD/DVD",
    "2B": "NET",
    "80": "NONE",
}

def parse_power(raw: str) -> str:
    if not raw:
        return "unknown"
    return "on" if raw.endswith("01") else "off" if raw.endswith("00") else "unknown"

def parse_volume(raw: str):
    if not raw:
        return None
    m = re.search(r"([0-9A-F]{2})$", raw)
    return int(m.group(1), 16) if m else None

def parse_input(raw: str):
    if not raw:
        return None
    code = raw[-2:].upper()
    return INPUT_CODE_MAP.get(code, code)

def _startup_zone_validation():
    ip = get_receiver_ip()
    try:
        with socket.create_connection((ip, 60128), timeout=0.35):
            print(f"[startup] receiver {ip} reachable on 60128")
    except Exception as e:
        print(f"[startup] receiver {ip} NOT reachable (60128) — {e}")

if os.environ.get("HOUSEAUDIO_SKIP_STARTUP") != "1":
    _startup_zone_validation()

# ---- Routes -------------------------------------------------------------------

@app.route("/status", methods=["GET"])
def status():
    st = mpd_control.get_status()
    return jsonify(st)

@app.route("/announce", methods=["POST"])
def announce_route():
    body = request.get_json(force=True)
    zone_name = body.get("zone")
    volume    = body.get("volume")          # int 0..100
    file_url  = body.get("file") or body.get("url")  # allow legacy key

    if not zone_name:
        return jsonify({"ok": False, "error": "missing 'zone'"}), 400
    if volume is None:
        return jsonify({"ok": False, "error": "missing 'volume'"}), 400
    if not file_url or not str(file_url).lower().startswith(("http://", "https://")):
        return jsonify({"ok": False, "error": "need http(s) 'file' URL"}), 400

    try:
        announce.play_zone_announcement(zone_name, int(volume), file_url)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/zone", methods=["POST"])
def zone():
    body = request.get_json(force=True)
    power = body.get("power")  # "on" | "off"

    if power not in ["on", "off"]:
        return jsonify({"ok": False, "error": "need power=on|off"}), 400

    resp = get_client().power(power == "on", zone="1")  # main zone power

    return jsonify({
        "ok": bool(resp and resp.startswith("!1PWR")),
        "sent": f"!1PWR{'01' if power == 'on' else '00'}",
        "stdout": resp or "",
    }), 200

@app.route("/zones/set", methods=["POST"])
def zones_set():
    """
    Body:
      {
        "zone_id": "1"|"2"|"3",
        "power": "on"|"off",         # optional
        "input": "03"|"05"|...,      # optional, hex SLI code (AUX=03, PC=05, NET=2B, NONE=80)
        "volume": 0-100              # optional, percent -> hex (receiver clamps >0x64)
      }
    """
    cli  = get_client()
    body = request.get_json(force=True)

    zid       = str(body.get("zone_id", "1"))
    power     = body.get("power")      # "on"/"off" or None
    input_hex = body.get("input")      # e.g., "03"
    vol_pct   = body.get("volume")     # 0..100 int

    results = {"zone_id": zid}

    def pct_to_hex(p):
        p = max(0, min(100, int(p)))
        return f"{p:02X}"  # AVR understands 00..64; >64 will be clamped

    # Apply power first (optional)
    if power in ("on", "off"):
        results["power_set"] = cli.power(power == "on", zone=zid) or ""

    # Input select (optional)
    if input_hex is not None:
        if not re.fullmatch(r"[0-9A-Fa-f]{2}", str(input_hex)):
            return jsonify({"ok": False, "error": "input must be 2-digit hex like '03'"}), 400
        results["input_set"] = cli.input_select(str(input_hex), zone=zid) or ""

    # Volume set (optional)
    if vol_pct is not None:
        try:
            hx = pct_to_hex(vol_pct)
        except Exception:
            return jsonify({"ok": False, "error": "volume must be int 0..100"}), 400
        results["volume_set"] = cli.volume_hex(hx, zone=zid) or ""

    # Current status snapshot
    results["status"] = {
        "power":  cli.power_query(zid)  or "",
        "input":  cli.input_query(zid)  or "",
        "volume": cli.volume_query(zid) or "",
    }
    return jsonify({"ok": True, **results})

@app.route("/zones/debug", methods=["GET"])
def zones_debug():
    """
    Return current input, volume, and power status for each zone in a readable form.
    """
    client = get_client()
    zones_cfg = announce.load_zones() or {}
    results = {}

    for name, cfg in zones_cfg.items():
        zid = str(cfg.get("zone_id", "1"))
        try:
            pwr_raw = client.power_query(zid)
            vol_raw = client.volume_query(zid)
            inp_raw = client.input_query(zid)

            results[name] = {
                "zone_id": zid,
                "power":  parse_power(pwr_raw),
                "volume": parse_volume(vol_raw),
                "input":  parse_input(inp_raw),
            }
        except Exception as e:
            results[name] = {"zone_id": zid, "error": str(e)}

    return jsonify(results)

if __name__ == "__main__":
    # local dev runner
    app.run(host="0.0.0.0", port=5001, debug=True)
