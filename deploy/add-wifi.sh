#!/bin/bash
# Save a WiFi network so the station joins it whenever it is in range.
#   sudo deploy/add-wifi.sh "Network name" "password" [priority]
# Higher priority wins when several saved networks are visible.
set -euo pipefail

SSID=${1:?network name}
PSK=${2:?password}
PRIO=${3:-0}
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
nmcli connection delete "$SSID" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname wlan0 con-name "$SSID" ssid "$SSID" \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
    connection.autoconnect yes connection.autoconnect-priority "$PRIO"
nmcli -f NAME,TYPE,AUTOCONNECT-PRIORITY connection show
