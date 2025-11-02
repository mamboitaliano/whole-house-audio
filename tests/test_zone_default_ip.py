# tests/test_zone_default_ip.py
import json, os
os.environ.setdefault("HOUSEAUDIO_SKIP_STARTUP", "1")
os.environ.setdefault("DEFAULT_RECEIVER_IP", "192.168.50.249")

from src.app import app

def test_zone_uses_default_receiver_ip(mocker):
    # Patch EISCPClient and its instance.power()
    mock_client_cls = mocker.patch("src.app.iscp.EISCPClient")
    mock_client = mock_client_cls.return_value
    mock_client.power.return_value = "!1PWR01"

    client = app.test_client()
    r = client.post("/zone", data=json.dumps({"power": "on"}), content_type="application/json")
    assert r.status_code == 200

    # Ensure client constructed with DEFAULT_RECEIVER_IP
    mock_client_cls.assert_called_once_with("192.168.50.249")
    # Ensure we powered main zone on
    mock_client.power.assert_called_once_with(True, zone="1")
