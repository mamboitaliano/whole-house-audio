# This file provides MPD control (pause/resume/status logic)
#
# What it does in production:
# - run mpc pause
# - run mpc play
# - parse mpc status

import subprocess

def run_cmd(cmd):
    """
    Run a shell command, capture stdout/stderr, return (rc, out, err).
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate()
    return proc.returncode, out.strip(), err.strip()

def pause_mpd():
    """
    Dispatch a 'pause' command to MPD
    """
    return run_cmd(["mpc", "pause"])

def resume_mpd():
    """
    Dispatch a 'resume' command to MPD
    """
    return run_cmd(["mpc", "play"])

def get_status():
    """
    Gets the status of MPD
    """
    rc, out, err = run_cmd(["mpc", "status"])
    return {
        "rc": rc,
        "raw": out,
        "err": err,
        "is_playing": "[playing]" in out,
        "is_paused": "[paused]" in out,
    }
