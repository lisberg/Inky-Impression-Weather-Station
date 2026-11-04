#!/bin/bash
# Pull the latest code and restart. Run over Tailscale SSH: sudo /opt/weather-station/deploy/update.sh
set -euo pipefail
APP=/opt/weather-station
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
git -C "$APP" pull --ff-only
"$APP/.venv/bin/pip" install --quiet -r "$APP/requirements.txt"
# older installs kept config.json in $APP, where the service can't save it
if [ -f "$APP/config.json" ] && [ ! -f "$APP/state/config.json" ]; then
    mv "$APP/config.json" "$APP/state/config.json"
    chown weather:weather "$APP/state/config.json"
fi
install -m 644 "$APP/deploy/weather-station.service" "$APP/deploy/weather-netwatch.service" /etc/systemd/system/
systemctl daemon-reload
systemctl restart weather-netwatch weather-station
systemctl --no-pager status weather-station | head -5
