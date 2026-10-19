#!/bin/bash
# Set up a fresh Raspberry Pi OS (Bookworm or later) as a weather station.
#   sudo git clone https://github.com/lisberg/Inky-Impression-Weather-Station.git /opt/weather-station
#   sudo /opt/weather-station/deploy/install.sh
# Safe to run again; it only adds what is missing.
set -euo pipefail

APP=/opt/weather-station
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
[ -f "$APP/station/app.py" ] || { echo "expected the repository at $APP"; exit 1; }

echo "== packages"
apt-get update
apt-get install -y git python3-venv python3-pil python3-requests python3-gpiozero \
    python3-lgpio network-manager iw avahi-daemon unattended-upgrades

echo "== SPI and I2C for the Inky panel"
raspi-config nonint do_spi 0
raspi-config nonint do_i2c 0
BOOT_CFG=/boot/firmware/config.txt
[ -f "$BOOT_CFG" ] || BOOT_CFG=/boot/config.txt
# the inky library drives chip select itself and needs the kernel to leave it alone
grep -q '^dtoverlay=spi0-0cs' "$BOOT_CFG" || echo 'dtoverlay=spi0-0cs' >> "$BOOT_CFG"

echo "== service user"
id weather >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin weather
for g in gpio spi i2c; do getent group "$g" >/dev/null && usermod -aG "$g" weather; done

echo "== python environment"
[ -d "$APP/.venv" ] || python3 -m venv --system-site-packages "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade -r "$APP/requirements.txt"

echo "== config"
mkdir -p "$APP/state"
[ -f "$APP/config.json" ] || cp "$APP/config.example.json" "$APP/config.json"
chown -R weather:weather "$APP/state" "$APP/config.json"
git config --system --add safe.directory "$APP"

echo "== keep logs small on the SD card"
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=50M\n' > /etc/systemd/journald.conf.d/weather-station.conf

echo "== automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== services"
install -m 644 "$APP/deploy/weather-station.service" /etc/systemd/system/
install -m 644 "$APP/deploy/weather-netwatch.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now weather-netwatch.service weather-station.service

echo
echo "Done. Edit $APP/config.json, then: sudo systemctl restart weather-station"
echo "If SPI was just enabled, reboot once: sudo reboot"
