import json
from src.app import app

def test_announce_rejects_non_http_urls():
    client = app.test_client()

    # missing URL
    r = client.post("/announce", data=json.dumps({}), content_type="application/json")
    assert r.status_code == 400

    # bad scheme
    r = client.post(
        "/announce",
        data=json.dumps({"url": "file:///tmp/a.wav"}),
        content_type="application/json",
    )
    assert r.status_code == 400
    assert b"http(s)" in r.data

    # good scheme (doesn't assert play success, just passes guard)
    r = client.post(
        "/announce",
        data=json.dumps({"url": "https://example.com/a.wav"}),
        content_type="application/json",
    )
    # could be 200 or 500 depending on announce.play_announcement mock; just ensure not blocked by the guard
    assert r.status_code in (200, 500)
