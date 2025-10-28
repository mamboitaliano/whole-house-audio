#!/usr/bin/env python3
"""
Entry point for running the house audio API service on the Pi
under systemd. This file lets us avoid relying on `flask run`
and keeps behavior consistent.
"""

from src.app import app

def main():
    # production-ish settings for the Pi
    # - host=0.0.0.0 so other devices on LAN can reach it
    # - debug=False so we don't do autoreload loops under systemd
    app.run(host="0.0.0.0", port=5001, debug=False)

if __name__ == "__main__":
    main()
