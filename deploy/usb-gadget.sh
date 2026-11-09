#!/bin/bash
# Turn the Pi Zero's data port (marked USB, not PWR) into a network link, so a
# laptop on the other end of the cable can reach it without any WiFi:
#   sudo /opt/weather-station/deploy/usb-gadget.sh && sudo reboot
#   ssh <user>@10.55.0.1        dashboard: http://10.55.0.1:8080
# The Pi hands the laptop an address, so nothing needs setting up on the laptop.
# Safe to run again; it only adds what is missing.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

BOOT=/boot/firmware
[ -f "$BOOT/config.txt" ] || BOOT=/boot

# the USB controller has to run as a device, not a host
grep -q '^dtoverlay=dwc2' "$BOOT/config.txt" || printf '\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n' >> "$BOOT/config.txt"
# load the ethernet gadget at boot (cmdline.txt is one single line)
grep -q 'modules-load=dwc2,g_ether' "$BOOT/cmdline.txt" ||
    sed -i '1 s/$/ modules-load=dwc2,g_ether/' "$BOOT/cmdline.txt"
# fixed addresses, so the laptop sees the same network adapter every boot
echo 'options g_ether host_addr=02:22:82:ff:ff:01 dev_addr=02:22:82:ff:ff:02' > /etc/modprobe.d/g_ether.conf

if ! nmcli -t -f NAME connection show | grep -qx usb-gadget; then
    nmcli connection add type ethernet ifname usb0 con-name usb-gadget \
        ipv4.method shared ipv4.addresses 10.55.0.1/24 ipv6.method link-local \
        connection.autoconnect yes
fi
echo "done; reboot, then plug the cable into the port marked USB"
