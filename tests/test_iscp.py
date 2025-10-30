# We'll mock the socket connect/send and assert the right bytes are being generated.
# Why this matters:
# You really don’t want to accidentally send the wrong zone volume command to all amps at 6AM.
# We catch these mistakes in CI, not in your yard speakers.
import src.iscp as iscp

def test_transact_packs_and_handles_response(mocker):
    # Patch socket.create_connection so we don't really open a socket
    fake_sock = mocker.MagicMock()
    # Craft a fake eISCP response for !1PWRQ like: "!1PWR01"
    payload = b"!1PWR01\r"
    data_size = len(payload).to_bytes(4, "big")
    header = b"ISCP" + (16).to_bytes(4, "big") + data_size + bytes([1]) + b"\x00\x00\x00"
    frame = header + payload

    # recv returns one frame once, then empty
    fake_sock.recv.side_effect = [frame]
    fake_conn_ctx = mocker.MagicMock()
    fake_conn_ctx.__enter__.return_value = fake_sock

    mocker.patch("socket.create_connection", return_value=fake_conn_ctx)

    cli = iscp.EISCPClient("192.0.2.10", 60128, timeout=0.1)
    out = cli.transact("!1PWRQ")
    assert out == "!1PWR01"

def test_send_iscp_shim_ok(mocker):
    # Ensure legacy API returns rc=0 on success path
    mocker.patch.object(iscp.EISCPClient, "transact", return_value="!1PWR01")
    rc, out, err = iscp.send_iscp("192.0.2.10", "!1PWRQ\r")
    assert rc == 0
    assert out == "!1PWR01"
    assert err == ""