#!/bin/bash
#
# redeploy.sh
#
# Usage:
#   ./redeploy.sh
#
# What it does:
#   - hard-resets any local changes
#   - pulls latest main from GitHub
#   - updates Python deps in the venv
#   - restarts the houseaudio systemd service
#
# This is meant to be run ON THE PI.
#

set -euo pipefail

REPO_DIR="/home/ubuntu/whole-house-audio"
VENV="$REPO_DIR/venv"
SERVICE_NAME="houseaudio.service"
BRANCH="main"
REMOTE="origin"

echo "[redeploy] cd $REPO_DIR"
cd "$REPO_DIR"

echo "[redeploy] git fetch $REMOTE $BRANCH"
git fetch "$REMOTE" "$BRANCH"

echo "[redeploy] resetting any local changes"
git reset --hard "FETCH_HEAD"

echo "[redeploy] installing/updating python deps"
source "$VENV/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "[redeploy] restarting $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "[redeploy] deployment complete."
sudo systemctl status "$SERVICE_NAME" --no-pager --full
