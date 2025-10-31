# src/iscp.py
import socket
from typing import Optional, Tuple
import time

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

    def _read_frame(self, s) -> str:
        """Read one eISCP frame; tolerate when recv() returns header+payload at once."""
        buf = b""
        # Read header (16 bytes), but allow over-read
        while len(buf) < 16:
            chunk = s.recv(16 - len(buf))
            if not chunk:
                return ""
            buf += chunk

        hdr = buf[:16]
        leftover = buf[16:]

        if hdr[:4] != ISCP_MAGIC:
            return ""

        data_len = int.from_bytes(hdr[8:12], "big")

        # Start payload with any leftover from the header read
        data = leftover
        while len(data) < data_len:
            chunk = s.recv(data_len - len(data))
            if not chunk:
                break
            data += chunk

        if data.endswith(CR):
            data = data[:-1]

        try:
            return data.decode("ascii", errors="ignore")
        except Exception:
            return ""
        
    def transact(self, ascii_cmd: str) -> str:
        """Back-compat shim for tests and callers that expect transact()."""
        return self._transact(ascii_cmd)

    def _transact(self, ascii_cmd: str, expect_prefix: str = None, read_window_s: float = 0.35) -> str:
        """
        Send ascii_cmd and read frames for a short window, returning:
          - the first frame that starts with expect_prefix (if provided), else
          - the first non-empty frame, else empty string.
        """
        pkt = _pack(ascii_cmd)
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.sendall(pkt)

            deadline = time.time() + read_window_s
            first_nonempty = ""
            matched = ""

            while time.time() < deadline:
                try:
                    # Use short per-read timeout to allow multiple frames
                    s.settimeout(0.12)
                    frame = self._read_frame(s)
                    if not frame:
                        # no more data for now; small sleep to wait for the next frame burst
                        time.sleep(0.02)
                        continue
                    if not first_nonempty:
                        first_nonempty = frame
                    if expect_prefix and frame.startswith(expect_prefix):
                        matched = frame
                        break
                except socket.timeout:
                    # brief idle; keep looping until deadline
                    continue
                except Exception:
                    break

            return matched or first_nonempty

    # ----- Zone-aware helpers (Onkyo/Integra pattern: main vs Z2 vs Z3)
    # Main: PWR/MVL/SLI/AMT ; Zone2: ZPW/ZVL/SLZ/ZMT ; Zone3: PW3/VL3/SL3/MT3
    def _cmds(self, zone: str):
        """Return the correct command names for the given zone."""
        z = str(zone)
        if z == "1":
            return {
                "PWR":  "PWR",   "PWRQ":  "PWRQSTN",
                "MVL":  "MVL",   "MVLQ":  "MVLQSTN",
                "SLI":  "SLI",   "SLIQ":  "SLIQSTN",
                "AMT":  "AMT",
            }
        if z == "2":
            return {
                "PWR":  "ZPW",   "PWRQ":  "ZPWQSTN",
                "MVL":  "ZVL",   "MVLQ":  "ZVLQSTN",
                "SLI":  "SLZ",   "SLIQ":  "SLZQSTN",
                "AMT":  "ZMT",
            }
        if z == "3":
            return {
                "PWR":  "PW3",   "PWRQ":  "PW3QSTN",
                "MVL":  "VL3",   "MVLQ":  "VL3QSTN",
                "SLI":  "SL3",   "SLIQ":  "SL3QSTN",
                "AMT":  "MT3",
            }
        # fallback to main
        return {
            "PWR":  "PWR",   "PWRQ":  "PWRQSTN",
            "MVL":  "MVL",   "MVLQ":  "MVLQSTN",
            "SLI":  "SLI",   "SLIQ":  "SLIQSTN",
            "AMT":  "AMT",
        }

    def power(self, on: bool, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['PWR']}{'01' if on else '00'}", expect_prefix=f"!1{c['PWR']}")

    def power_query(self, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['PWRQ']}", expect_prefix=f"!1{c['PWR']}")

    def volume_hex(self, hex_00_64: str, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['MVL']}{hex_00_64.upper()}", expect_prefix=f"!1{c['MVL']}")

    def volume_query(self, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['MVLQ']}", expect_prefix=f"!1{c['MVL']}")

    def mute(self, on: bool, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['AMT']}{'01' if on else '00'}", expect_prefix=f"!1{c['AMT']}")

    def input_select(self, sli_code_hex: str, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['SLI']}{sli_code_hex.upper()}", expect_prefix=f"!1{c['SLI']}")

    def input_query(self, zone: str = "1"):
        c = self._cmds(zone)
        return self._transact(f"!1{c['SLIQ']}", expect_prefix=f"!1{c['SLI']}")

# Back-compat legacy API used by your routes/tests
def send_iscp(ip: str, payload: str) -> Tuple[int, str, str]:
    try:
        ascii_cmd = payload[:-1] if payload.endswith("\r") else payload
        resp = EISCPClient(ip).transact(ascii_cmd)
        return (0, resp or "", "")
    except Exception as e:
        return (1, "", str(e))
