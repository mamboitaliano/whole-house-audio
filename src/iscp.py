# src/iscp.py
import socket
from typing import Optional, Tuple

ISCP_MAGIC = b"ISCP"
ISCP_VER = 0x01
CR = b"\x0d"
DEFAULT_TIMEOUT = 2.0

def _pack(data_ascii: str) -> bytes:
    if not data_ascii.endswith("\r"):
        data = data_ascii.encode("ascii") + CR
    else:
        data = data_ascii.encode("ascii")
    header = (
        ISCP_MAGIC
        + (16).to_bytes(4, "big")
        + len(data).to_bytes(4, "big")
        + bytes([ISCP_VER])
        + b"\x00\x00\x00"
    )
    return header + data

def _unpack(buf: bytes) -> str:
    if len(buf) < 16 or buf[:4] != ISCP_MAGIC:
        return ""
    n = int.from_bytes(buf[8:12], "big")
    p = buf[16:16+n]
    if p.endswith(CR):
        p = p[:-1]
    return p.decode("ascii", errors="ignore")

class EISCPClient:
    def __init__(self, host: str, port: int = 60128, timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout

    def transact(self, ascii_cmd: str) -> Optional[str]:
        pkt = _pack(ascii_cmd)
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.sendall(pkt)
            try:
                buf = s.recv(4096)
                if not buf:
                    return None
                return _unpack(buf)
            except socket.timeout:
                return None

    # ----- Zone-aware helpers (Onkyo/Integra pattern: main vs Z2 vs Z3)
    # Main: PWR/MVL/SLI/AMT ; Zone2: ZPW/ZVL/SLZ/ZMT ; Zone3: PW3/VL3/SL3/MT3
    def _cmds(self, zone: str):
        """Return the correct command names for the given zone."""
        z = str(zone)
        if z == "1":
            return {
                "PWR": "PWR",  "PWRQ": "PWRQ",
                "MVL": "MVL",  "MVLQ": "MVLQ",
                "SLI": "SLI",  "SLIQ": "SLIQ",
                "AMT": "AMT",
            }
        if z == "2":
            return {
                "PWR": "ZPW",  "PWRQ": "ZPWQ",
                "MVL": "ZVL",  "MVLQ": "ZVLQ",
                "SLI": "SLZ",  "SLIQ": "SLZQ",
                "AMT": "ZMT",
            }
        if z == "3":
            return {
                "PWR": "PW3",  "PWRQ": "PW3Q",
                "MVL": "VL3",  "MVLQ": "VL3Q",
                "SLI": "SL3",  "SLIQ": "SL3Q",
                "AMT": "MT3",
            }
        # Fallback to main zone semantics
        return {
            "PWR": "PWR",  "PWRQ": "PWRQ",
            "MVL": "MVL",  "MVLQ": "MVLQ",
            "SLI": "SLI",  "SLIQ": "SLIQ",
            "AMT": "AMT",
        }

    def power(self, on: bool, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['PWR']}{'01' if on else '00'}")

    def power_query(self, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['PWRQ']}")

    def volume_hex(self, hex_00_64: str, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['MVL']}{hex_00_64.upper()}")

    def volume_query(self, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['MVLQ']}")

    def mute(self, on: bool, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['AMT']}{'01' if on else '00'}")

    def input_select(self, sli_code_hex: str, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['SLI']}{sli_code_hex.upper()}")

    def input_query(self, zone: str = "1"):
        c = self._cmds(zone)
        return self.transact(f"!1{c['SLIQ']}")

# Back-compat legacy API used by your routes/tests
def send_iscp(ip: str, payload: str) -> Tuple[int, str, str]:
    try:
        ascii_cmd = payload[:-1] if payload.endswith("\r") else payload
        resp = EISCPClient(ip).transact(ascii_cmd)
        return (0, resp or "", "")
    except Exception as e:
        return (1, "", str(e))
