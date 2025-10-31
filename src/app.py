# Flask routes only

from flask import Flask, jsonify, request
import os
import socket

from . import mpd_control, playback, iscp
from . import deploy
from .helpers import announce

app = Flask(__name__)

# default receiver if /zone omits receiver_ip
DEFAULT_RECEIVER_IP = os.environ.get("DEFAULT_RECEIVER_IP", "192.168.50.249")

def _startup_zone_validation():
    """Load zones.yaml and log which receivers respond on 60128."""
    
    try:
        zones = announce.load_zones() or {}
        if not zones:
            print("[startup] zones.yaml: no zones configured")
            return
        print(f"[startup] zones.yaml loaded: {list(zones.keys())}")
        for name, cfg in zones.items():
            ip = (cfg or {}).get("receiver_ip")
            if not ip:
                print(f"[startup] zone '{name}': no receiver_ip set")
                continue
            try:
                with socket.create_connection((ip, 60128), timeout=0.35):
                    print(f"[startup] zone '{name}': {ip} reachable on 60128")
            except Exception as e:
                print(f"[startup] zone '{name}': {ip} NOT reachable (60128) — {e}")
    except Exception as e:
        print(f"[startup] zones validation error: {e}")

if os.environ.get("HOUSEAUDIO_SKIP_STARTUP") != "1":
    _startup_zone_validation()

@app.route("/status", methods=["GET"])
def status():
    st = mpd_control.get_status()
    return jsonify(st)

@app.route("/announce", methods=["POST"])
def announce_route():
    body = request.get_json(force=True)
    zone_name = body.get("zone")
    volume = body.get("volume")          # int 0..100
    file_url = body.get("file")

    if not zone_name:
        return jsonify({"ok": False, "error": "missing 'zone'"}), 400
    if volume is None:
        return jsonify({"ok": False, "error": "missing 'volume'"}), 400
    if not file_url or not str(file_url).lower().startswith(("http://", "https://")):
        return jsonify({"ok": False, "error": "need http(s) 'file' URL"}), 400

    try:
        from .helpers import announce
        announce.play_zone_announcement(zone_name, int(volume), file_url)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/zone", methods=["POST"])
def zone():
    body = request.get_json(force=True)
    ip = body.get("receiver_ip") or DEFAULT_RECEIVER_IP
    power = body.get("power")

    if power not in ["on", "off"]:
        return jsonify({"ok": False, "error": "need power=on|off"}), 400
    if not ip:
        return jsonify({"ok": False, "error": "receiver_ip missing and DEFAULT_RECEIVER_IP not set"}), 400

    cmd = "!1PWR01\r" if power == "on" else "!1PWR00\r"
    rc, out, err = iscp.send_iscp(ip, cmd)

    return jsonify({
        "ok": (rc == 0),
        "sent": cmd.strip(),
        "rc": rc,
        "stdout": out,
        "stderr": err
    }), (200 if rc == 0 else 500)

@app.route("/deploy", methods=["POST"])
def deploy_route():
    raw = request.get_data()  # bytes
    sig = request.headers.get("X-Houseaudio-Signature", "")
    secret = os.environ.get("DEPLOY_SECRET", "")

    if not deploy.verify_signature(secret, raw, sig):
        return jsonify({"ok": False, "error": "bad signature"}), 403

    result = deploy.do_deploy()
    return jsonify(result)

@app.route("/zones/debug", methods=["GET"])
def zones_debug():
    """
    Return current input, volume, and power status for each zone in a readable form.
    """
    from .helpers import announce
    from . import iscp
    import os, re

    ip = os.environ.get("DEFAULT_RECEIVER_IP", "192.168.50.249")
    client = iscp.EISCPClient(ip)
    zones = announce.load_zones() or {}
    results = {}

    def parse_power(raw):
        if not raw:
            return "unknown"
        return "on" if raw.endswith("01") else "off" if raw.endswith("00") else raw

    def parse_volume(raw):
        if not raw:
            return None
        # last two hex digits -> 0–100 scale (00–64)
        m = re.search(r"([0-9A-F]{2})$", raw)
        if not m:
            return None
        val = int(m.group(1), 16)
        pct = round(val * 100 / 100) if val <= 100 else val
        return pct

    def parse_input(raw):
        if not raw:
            return None
        code = raw[-2:].upper()
        mapping = {
            "00": "TV",
            "02": "GAME",
            "03": "AUX",
            "05": "PC",
            "10": "BD/DVD",
            "2B": "NET",
        }
        return mapping.get(code, code)

    for name, cfg in zones.items():
        zid = str(cfg.get("zone_id", "1"))
        try:
            pwr_raw = client.power_query(zid)
            vol_raw = client.volume_query(zid)
            inp_raw = client.transact(
                f"!{zid}{('SLIQ' if zid=='1' else ('SLZQ' if zid=='2' else 'SL3Q'))}"
            )

            results[name] = {
                "zone_id": zid,
                "power": parse_power(pwr_raw),
                "volume": parse_volume(vol_raw),
                "input": parse_input(inp_raw),
            }
        except Exception as e:
            results[name] = {"zone_id": zid, "error": str(e)}

    return jsonify(results)

if __name__ == "__main__":
    # local dev runner
    app.run(host="0.0.0.0", port=5001, debug=True)
