# ISCP receiver control (TCP commands to the receivers)
# What it does in production:
# - open a TCP connection to 192.168.50.x:60128
# - send strings like !1PWR01\r

import subprocess

def send_iscp(ip, payload):
    """
    Send an ISCP command string like '!1PWR01\\r' to a given receiver IP.
    Uses netcat.
    """
    cmd = ["nc", ip, "60128"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate(payload)
    return proc.returncode, out.strip(), err.strip()
