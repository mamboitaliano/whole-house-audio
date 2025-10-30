# src/iscp.py
# Proper eISCP (TCP, port 60128) with pack/unpack.
# Backwards-compatible send_iscp(ip, payload) that accepts payloads like "!1PWR01\r"

import socket
from typing import Optional, Tuple

ISCP_MAGIC = b"ISCP"
ISCP_VER = 0x01
CR = b"\x0d"

DEFAULT_TIMEOUT = 2.0  # seconds

# Common command prefixes
PWR = "PWR"  # 00 off, 01 on
MVL = "MVL"  # volume hex 00..64
AMT = "AMT"  # mute 00 off, 01 on
SLI = "SLI"  # input selector (model-specific codes)


class EISCPClient:
    def __init__(self, host: str, port: int = 60128, timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout

    @staticmethod
    def _pack(data_ascii: str) -> bytes:
        """
        Build a full eISCP frame around ASCII data (ensure CR).
        data_ascii example: "!1PWR01" or "!1MVLQ"
        """
        if not data_ascii.endswith("\r"):
            data = data_ascii.encode("ascii") + CR
        else:
            data = data_ascii.encode("ascii")
        header_size = 16
        data_size = len(data)
        header = (
            ISCP_MAGIC
            + header_size.to_bytes(4, "big")
            + data_size.to_bytes(4, "big")
            + bytes([ISCP_VER])
            + b"\x00\x00\x00"
        )
        return header + data

    @staticmethod
    def _unpack(buf: bytes) -> str:
        """Return ASCII data (without trailing CR) if this looks like an eISCP frame."""
        if len(buf) < 16 or buf[:4] != ISCP_MAGIC:
            return ""
        data_len = int.from_bytes(buf[8:12], "big")
        payload = buf[16 : 16 + data_len]
        if payload.endswith(CR):
            payload = payload[:-1]
        try:
            return payload.decode("ascii", errors="ignore")
        except Exception:
            return ""

    def transact(self, ascii_cmd: str) -> Optional[str]:
        """
        Send a single ASCII command like '!1PWRQ' or '!1PWR01' and return
        the first response frame's ASCII payload (or None on timeout/no data).
        """
        pkt = self._pack(ascii_cmd)
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.sendall(pkt)
            try:
                buf = s.recv(4096)
                if not buf:
                    return None
                return self._unpack(buf)
            except socket.timeout:
                return None

    # --- convenience helpers -------------------------------------------------

    def power(self, on: bool, zone: str = "1") -> Optional[str]:
        return self.transact(f"!{zone}{PWR}{'01' if on else '00'}")

    def power_query(self, zone: str = "1") -> Optional[str]:
        return self.transact(f"!{zone}{PWR}Q")

    def volume_hex(self, hex_00_64: str, zone: str = "1") -> Optional[str]:
        return self.transact(f"!{zone}{MVL}{hex_00_64.upper()}")

    def volume_query(self, zone: str = "1") -> Optional[str]:
        return self.transact(f"!{zone}{MVL}Q")

    def mute(self, on: bool, zone: str = "1") -> Optional[str]:
        return self.transact(f"!{zone}{AMT}{'01' if on else '00'}")

    def input_select(self, sli_code_hex: str, zone: str = "1") -> Optional[str]:
        # e.g., "2B" for NET depending on model mappings
        return self.transact(f"!{zone}{SLI}{sli_code_hex.upper()}")


# --- compatibility shim for existing code -------------------------------------

def send_iscp(ip: str, payload: str) -> Tuple[int, str, str]:
    """
    Backward-compatible wrapper used by announce.py/app.py right now.
    Accepts a raw ISCP ASCII data string like '!1PWR01\\r' or '!1SLI2B\\r'.
    Builds the full eISCP frame, sends it, and returns (rc, out, err).
    rc == 0 means 'sent OK'. 'out' is the ASCII response payload (no CR) if any.
    """
    try:
        # Trim any trailing CR to normalize
        ascii_cmd = payload[:-1] if payload.endswith("\r") else payload
        cli = EISCPClient(ip)
        resp = cli.transact(ascii_cmd)
        return (0, resp or "", "")
    except Exception as e:
        return (1, "", str(e))
