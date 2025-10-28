# We'll mock the socket connect/send and assert the right bytes are being generated.

# Why this matters:
# You really don’t want to accidentally send the wrong zone volume command to all amps at 6AM.
# We catch these mistakes in CI, not in your yard speakers.