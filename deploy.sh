#!/bin/bash
# Navigator deploy script — push to git, pull on OVH, restart service

set -e

OVH_HOST="ubuntu@15.204.75.156"
OVH_KEY="/home/hyperion/.ssh/hearthmind_ovh_rsa"

echo "[deploy] Pushing to git..."
cd /home/hyperion/hearthmind/navigator
git add -A
git commit -m "deploy-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || echo "[deploy] Nothing new to commit"
git push origin main

echo "[deploy] Pulling on OVH..."
ssh -i $OVH_KEY $OVH_HOST "cd ~/hearthmind-navigator && git pull origin main"

echo "[deploy] Restarting service..."
ssh -i $OVH_KEY $OVH_HOST "sudo systemctl restart navigator"

echo "[deploy] Done. Navigator live at http://15.204.75.156:5000"
