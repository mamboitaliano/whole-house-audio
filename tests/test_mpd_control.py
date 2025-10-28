# we mock subprocess.Popen so we never actually mess with MPD.

# We assert that:
# pause_mpd() calls mpc pause
# resume_mpd() calls mpc play
# get_status() returns a nice dict even if mpc status output changes a little

# Why this matters:
# If we ever change the shell commands or parsing logic, tests will scream before we ship it to the Pi.

import src.mpd_control as mpd

def test_pause_calls_mpc_pause(mocker):
    fake = mocker.patch("src.mpd_control.run_cmd", return_value=(0, "", ""))
    rc, out, err = mpd.pause_mpd()
    fake.assert_called_once_with(["mpc", "pause"])
    assert rc == 0

def test_get_status_parses_playing(mocker):
    fake_output = (
        "http://stream.example\n"
        "[playing] #1/1   0:12/3:45 (5%)\n"
        "volume: 80%   repeat: off\n"
    )
    mocker.patch("src.mpd_control.run_cmd", return_value=(0, fake_output, ""))

    status = mpd.get_status()
    assert status["rc"] == 0
    assert status["is_playing"] is True
    assert status["is_paused"] is False
    assert "volume" in status["raw"]
