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
    def _prefixes(self, zone: str):
        z = str(zone)
        if z == "1":
            return ("PWR", "MVL", "SLI", "AMT", "PWRQ", "MVLQ", "SLIQ")
        if z == "2":
            return ("ZPW", "ZVL", "SLZ", "ZMT", "ZPWQ", "ZVLQ", "SLZQ")
        if z == "3":
            return ("PW3", "VL3", "SL3", "MT3", "PW3Q", "VL3Q", "SL3Q")
        # fallback: treat as main
        return ("PWR", "MVL", "SLI", "AMT", "PWRQ", "MVLQ", "SLIQ")

    def power(self, on: bool, zone: str = "1"):        # on/off
        PWR, *_ = self._prefixes(zone)
        return self.transact(f"!{zone}{PWR}{'01' if on else '00'}")

    def power_query(self, zone: str = "1"):
        *_, PWRQ, _, _ = self._prefixes(zone)
        # PWRQ symbol is in the tuple above at index 4
        return self.transact(f"!{zone}{PWRQ}")

    def volume_hex(self, hex_00_64: str, zone: str = "1"):
        _, MVL, *_ = self._prefixes(zone)
        return self.transact(f"!{zone}{MVL}{hex_00_64.upper()}")

    def volume_query(self, zone: str = "1"):
        *_, _, MVLQ, _ = self._prefixes(zone)
        return self.transact(f"!{zone}{MVLQ}")

    def mute(self, on: bool, zone: str = "1"):
        *_, AMT, _, _, _ = self._prefixes(zone)
        return self.transact(f"!{zone}{AMT}{'01' if on else '00'}")

    def input_select(self, sli_code_hex: str, zone: str = "1"):
        *_, _, _, SLI = self._prefixes(zone)
        return self.transact(f"!{zone}{SLI}{sli_code_hex.upper()}")

# Back-compat legacy API used by your routes/tests
def send_iscp(ip: str, payload: str) -> Tuple[int, str, str]:
    try:
        ascii_cmd = payload[:-1] if payload.endswith("\r") else payload
        resp = EISCPClient(ip).transact(ascii_cmd)
        return (0, resp or "", "")
    except Exception as e:
        return (1, "", str(e))
