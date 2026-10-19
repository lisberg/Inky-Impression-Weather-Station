#!/bin/bash
# Pull the latest code and restart. Run over Tailscale SSH: sudo /opt/weather-station/deploy/update.sh
set -euo pipefail
APP=/opt/weather-station
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
git -C "$APP" pull --ff-only
"$APP/.venv/bin/pip" install --quiet -r "$APP/requirements.txt"
install -m 644 "$APP/deploy/weather-station.service" "$APP/deploy/weather-netwatch.service" /etc/systemd/system/
systemctl daemon-reload
systemctl restart weather-netwatch weather-station
systemctl --no-pager status weather-station | head -5
