#!/bin/bash
# Join this station to your tailnet so you can reach it from anywhere.
#   sudo deploy/tailscale.sh tskey-auth-XXXX [hostname]
# Make the key at https://login.tailscale.com/admin/settings/keys. Then, in the
# admin console, open the machine and choose "Disable key expiry", or it will
# drop off the tailnet after 180 days.
set -euo pipefail

KEY=${1:-${TS_AUTHKEY:-}}
NAME=${2:-$(hostname)}
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
[ -n "$KEY" ] || { echo "usage: sudo $0 <auth key> [hostname]"; exit 1; }

command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
# --ssh lets you log in with your Tailscale identity, no keys or passwords to manage
tailscale up --auth-key="$KEY" --hostname="$NAME" --ssh
tailscale status --self --peers=false
echo "Reach it at: ssh ${SUDO_USER:-pi}@$NAME   (or via the IP above)"
