"""Best-effort facts about the network, for the info and setup screens.

Every helper returns None instead of raising: a missing tool or a dead
network must never stop the screen from drawing.
"""
import json
import os
import socket
import subprocess

from .config import STATE_DIR

HOTSPOT_FILE = os.path.join(STATE_DIR, "hotspot.json")


def _run(*cmd, timeout=5):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def hostname():
    return socket.gethostname()


def local_ips():
    out = _run("hostname", "-I")
    if not out:
        return []
    # skip the Tailscale CGNAT range and IPv6, which are shown separately
    return [ip for ip in out.split() if ":" not in ip and not ip.startswith("100.")]


def wifi_ssid():
    out = _run("nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi")
    for line in (out or "").splitlines():
        active, _, ssid = line.partition(":")
        if active == "yes":
            return ssid.replace("\\:", ":")
    return None


def tailscale():
    """Return {"ip", "name", "online"} or None when Tailscale isn't installed/up."""
    out = _run("tailscale", "status", "--json")
    if not out:
        return None
    try:
        me = json.loads(out).get("Self") or {}
    except ValueError:
        return None
    ips = [ip for ip in me.get("TailscaleIPs") or [] if ":" not in ip]
    return {"ip": ips[0] if ips else None,
            "name": (me.get("DNSName") or "").rstrip(".") or me.get("HostName"),
            "online": bool(me.get("Online"))}


def hotspot():
    """The setup hotspot's details while it is up, else None (written by netwatch)."""
    try:
        with open(HOTSPOT_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def summary():
    return {"hostname": hostname(), "ips": local_ips(), "ssid": wifi_ssid(),
            "tailscale": tailscale(), "hotspot": hotspot()}
