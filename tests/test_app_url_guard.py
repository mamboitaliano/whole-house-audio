import json
import os
os.environ.setdefault("HOUSEAUDIO_SKIP_STARTUP", "1")
from src.app import app

def test_announce_rejects_non_http_urls():
    client = app.test_client()

    # missing URL (any missing required field should 400)
    r = client.post("/announce", data=json.dumps({}), content_type="application/json")
    assert r.status_code == 400

    # bad scheme -> include zone+volume so we hit the URL guard
    r = client.post(
        "/announce",
        data=json.dumps({
            "zone": "inside",
            "volume": 50,
            "url": "file:///tmp/a.wav"
        }),
        content_type="application/json",
    )
    assert r.status_code == 400
    assert b"http(s)" in r.data  # now it should be the URL guard message

    # good scheme (not asserting success of playback here)
    r = client.post(
        "/announce",
        data=json.dumps({
            "zone": "inside",
            "volume": 50,
            "file": "https://example.com/a.wav"
        }),
        content_type="application/json",
    )
    assert r.status_code in (200, 500)
