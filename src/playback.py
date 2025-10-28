# Playback (play_audio_file, etc.)
# invokes ffplay to play the temp WAV/mp3 you POSTed to /announce

import subprocess

def play_audio_file(path):
    """
    Play an audio file synchronously using ffplay (no GUI).
    """
    cmd = [
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-loglevel", "quiet",
        path,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate()
    return proc.returncode, out.strip(), err.strip()
