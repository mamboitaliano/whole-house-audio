import json
import os
from src.app import app

def test_zone_uses_default_receiver_ip(monkeypatch, mocker):
    # ensure env default for this test
    monkeypatch.setenv("DEFAULT_RECEIVER_IP", "192.168.50.249")

    # mock send_iscp so we don't actually talk to a receiver
    fake = mocker.patch("src.iscp.send_iscp", return_value=(0, "", ""))

    client = app.test_client()
    r = client.post(
        "/zone",
        data=json.dumps({"power": "on"}),  # no receiver_ip provided
        content_type="application/json",
    )
    assert r.status_code == 200

    # Confirm default IP was used
    args, kwargs = fake.call_args
    assert args[0] == "192.168.50.249"
