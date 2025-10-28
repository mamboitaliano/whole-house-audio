# Deployment hook
# /deploy logic (git pull, restart)
# validates HMAC signature
# runs git pull, pip install, systemctl restart

import hmac
import hashlib
import subprocess

def verify_signature(secret: str, body: bytes, sent_sig: str) -> bool:
    """
    Check HMAC signature. sent_sig should look like 'sha256=<hex>'
    """
    if not secret:
        return False
    if not sent_sig or not sent_sig.startswith("sha256="):
        return False

    sent_hash = sent_sig.split("=", 1)[1]
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sent_hash)

def run_cmd(cmd):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate()
    return proc.returncode, out.strip(), err.strip()

def do_deploy():
    """
    This will eventually:
      - git pull
      - pip install -r requirements.txt
      - systemctl restart houseaudio.service
    We'll flesh it out later on the Pi.
    For now it's just a stub to prove wiring.
    """
    return {
        "ok": True,
        "detail": "stubbed deploy"
    }
