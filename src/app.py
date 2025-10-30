# Flask routes only

from flask import Flask, jsonify, request
import os

from . import mpd_control
from . import playback
from . import iscp
from . import deploy
from .helpers import announce

app = Flask(__name__)

@app.route("/status", methods=["GET"])
def status():
    st = mpd_control.get_status()
    return jsonify(st)

@app.route("/announce", methods=["POST"])
def announce_route():
    body = request.get_json(force=True)
    url = body.get("url")
    volume = body.get("volume")
    zone = body.get("zone")
    resume = body.get("resume", True)

    if not url:
        return jsonify({"ok": False, "error": "need url"}), 400

    try:
        announce.play_announcement(url, volume, zone, resume)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/zone", methods=["POST"])
def zone():
    body = request.get_json(force=True)
    ip = body.get("receiver_ip")
    power = body.get("power")

    if not ip or power not in ["on", "off"]:
        return jsonify({"ok": False, "error": "need receiver_ip and power=on|off"}), 400

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

if __name__ == "__main__":
    # local dev runner
    app.run(host="0.0.0.0", port=5001, debug=True)
