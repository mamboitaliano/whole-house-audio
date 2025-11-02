# src/iscp.py
import socket
import struct
from typing import Optional, Tuple

ISCP_MAGIC = b"ISCP"
ISCP_VER   = 1
CR         = b"\r"
EM         = b"\x1a"   # Integra often appends 0x1A (EM) before CRLF

DEFAULT_TIMEOUT = 2.0
DEFAULT_PORT = 60128

# ---------- low-level eISCP framing ----------

def _build_eiscp(bare_cmd: str) -> bytes:
    """
    Wrap bare ASCII command (e.g., 'PWRQSTN', 'ZPWQSTN', 'PWR01') into eISCP.
    Always prefix '!1' and suffix CR in the payload.
    """
    payload = ("!1" + bare_cmd).encode("ascii")
    if not payload.endswith(CR):
        payload += CR
    header  = ISCP_MAGIC
    header += struct.pack(">I", 16)                 # header size
    header += struct.pack(">I", len(payload))       # data size
    header += bytes([ISCP_VER, 0x00, 0x00, 0x00])   # version + reserved
    return header + payload

def _read_one_frame(sock: socket.socket, timeout: float = 2.0) -> Optional[str]:
    """
    Read a single eISCP frame and return the ASCII payload without trailing 0x1A/CR/LF.
    Returns None on EOF or invalid header.
    """
    sock.settimeout(timeout)

    # Read 16-byte header (allow partial reads)
    hdr = b""
    while len(hdr) < 16:
        chunk = sock.recv(16 - len(hdr))
        if not chunk:
            return None
        hdr += chunk

    if hdr[:4] != ISCP_MAGIC:
        return None

    data_len = int.from_bytes(hdr[8:12], "big")

    # Read payload (allow partial reads)
    data = b""
    while len(data) < data_len:
        chunk = sock.recv(data_len - len(data))
        if not chunk:
            break
        data += chunk

    # Strip trailing EM(0x1A), CR, LF if present
    data = data.rstrip(b"\r\n")
    if data.endswith(EM):
        data = data[:-1]
    data = data.rstrip(b"\r\n")

    try:
        return data.decode("ascii", errors="ignore")
    except Exception:
        return None

def _transact_one(host: str, port: int, bare_cmd: str, expect_prefix: str, window_s: float = 1.0, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
    """
    Open a connection, send one command (QSTN or SET), and return the first frame
    that starts with expect_prefix (e.g., '!1ZPW', '!1VL3'). Ignores unrelated frames.
    """
    pkt = _build_eiscp(bare_cmd)
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(pkt)
        # Read for a short window — ignoring unsolicited frames
        s.settimeout(0.2)
        import time
        deadline = time.time() + window_s
        while time.time() < deadline:
            try:
                frame = _read_one_frame(s, timeout=0.2)
                if not frame:
                    continue
                if frame.startswith(expect_prefix):
                    return frame
            except socket.timeout:
                continue
            except Exception:
                break
    return None

# ---------- zone-aware helpers ----------

def _cmds(zone: str):
    """
    Map logical zone to command families:
      Zone 1 (main):  PWR/MVL/SLI/AMT + QSTN forms
      Zone 2:         ZPW/ZVL/SLZ/ZMT + QSTN forms
      Zone 3:         PW3/VL3/SL3/MT3 + QSTN forms
    """
    z = str(zone)
    if z == "1":
        return {
            "PWR": "PWR",  "PWRQ": "PWRQSTN",
            "MVL": "MVL",  "MVLQ": "MVLQSTN",
            "SLI": "SLI",  "SLIQ": "SLIQSTN",
            "AMT": "AMT",
        }
    if z == "2":
        return {
            "PWR": "ZPW",  "PWRQ": "ZPWQSTN",
            "MVL": "ZVL",  "MVLQ": "ZVLQSTN",
            "SLI": "SLZ",  "SLIQ": "SLZQSTN",
            "AMT": "ZMT",
        }
    if z == "3":
        return {
            "PWR": "PW3",  "PWRQ": "PW3QSTN",
            "MVL": "VL3",  "MVLQ": "VL3QSTN",
            "SLI": "SL3",  "SLIQ": "SL3QSTN",
            "AMT": "MT3",
        }
    # fallback to main
    return {
        "PWR": "PWR",  "PWRQ": "PWRQSTN",
        "MVL": "MVL",  "MVLQ": "MVLQSTN",
        "SLI": "SLI",  "SLIQ": "SLIQSTN",
        "AMT": "AMT",
    }

# ---------- public class (matches your existing app usage) ----------

class EISCPClient:
    def __init__(self, host: str, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout

    # Back-compat for tests / callers that used cli.transact("!1XXX..")
    def transact(self, ascii_cmd: str) -> Optional[str]:
        # Allow callers to pass either bare ("PWRQSTN") or framed ("!1PWRQSTN")
        bare = ascii_cmd
        if ascii_cmd.startswith("!1"):
            bare = ascii_cmd[2:]
        # Best-effort: expect the first 4 letters of the command family
        family = bare[:3] if bare[:3] in ("PWR","ZPW","PW3","MVL","ZVL","VL3","SLI","SLZ","SL3","AMT","ZMT","MT3") else bare[:3]
        expect = "!1" + family
        return _transact_one(self.host, self.port, bare, expect_prefix=expect, timeout=self.timeout)

    # Explicit helpers
    def power(self, on: bool, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, f"{c['PWR']}{'01' if on else '00'}", expect_prefix=f"!1{c['PWR']}", timeout=self.timeout)

    def power_query(self, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, c['PWRQ'], expect_prefix=f"!1{c['PWR']}", timeout=self.timeout)

    def volume_hex(self, hex_00_64: str, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, f"{c['MVL']}{hex_00_64.upper()}", expect_prefix=f"!1{c['MVL']}", timeout=self.timeout)

    def volume_query(self, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, c['MVLQ'], expect_prefix=f"!1{c['MVL']}", timeout=self.timeout)

    def mute(self, on: bool, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, f"{c['AMT']}{'01' if on else '00'}", expect_prefix=f"!1{c['AMT']}", timeout=self.timeout)

    def input_select(self, sli_code_hex: str, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, f"{c['SLI']}{sli_code_hex.upper()}", expect_prefix=f"!1{c['SLI']}", timeout=self.timeout)

    def input_query(self, zone: str = "1"):
        c = _cmds(zone)
        return _transact_one(self.host, self.port, c['SLIQ'], expect_prefix=f"!1{c['SLI']}", timeout=self.timeout)

    def query_zone_status(self, zone: str, window_s: float = 1.0):
        """
        Query power, volume, input sequentially (one command at a time) reusing the same logic.
        Returns {"power": "...", "volume": "...", "input": "..."} raw frames (or "" if none).
        """
        got = {
            "power":  self.power_query(zone)  or "",
            "volume": self.volume_query(zone) or "",
            "input":  self.input_query(zone)  or "",
        }
        return got
