"""Saved and visible WiFi networks, through NetworkManager's nmcli.

The service user is allowed to manage NetworkManager by the polkit rule that
deploy/install.sh installs.
"""
import json
import os
import subprocess
import threading
import time

from .config import STATE_DIR

IFACE = "wlan0"
SCAN_FILE = os.path.join(STATE_DIR, "scan.json")
SETUP_CON = "station-setup"


class WifiError(RuntimeError):
    pass


def nmcli(*args, timeout=30):
    try:
        out = subprocess.run(("nmcli",) + args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WifiError(str(exc)) from exc
    if out.returncode:
        raise WifiError(out.stderr.strip() or "nmcli failed")
    return out.stdout


def split_terse(line):
    """Split one line of `nmcli -t` output, where ':' inside a value is escaped as '\\:'."""
    fields, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def saved(run=nmcli):
    """Saved WiFi networks, highest priority first: [{name, ssid, priority, active}]."""
    rows = []
    for line in run("-t", "-f", "NAME,TYPE,ACTIVE", "connection", "show").splitlines():
        name, ctype, active = (split_terse(line) + ["", ""])[:3]
        if ctype != "802-11-wireless" or name == SETUP_CON:
            continue
        detail = run("-t", "-g", "802-11-wireless.ssid,connection.autoconnect-priority",
                     "connection", "show", name).splitlines()
        ssid = detail[0] if detail else name
        try:
            prio = int(detail[1]) if len(detail) > 1 else 0
        except ValueError:
            prio = 0
        rows.append({"name": name, "ssid": ssid, "priority": prio, "active": active == "yes"})
    return sorted(rows, key=lambda r: (-r["priority"], r["name"].lower()))


def _parse_scan(text):
    best = {}
    for line in text.splitlines():
        ssid, signal, security = (split_terse(line) + ["", ""])[:3]
        if not ssid:
            continue
        try:
            signal = int(signal)
        except ValueError:
            signal = 0
        if ssid not in best or signal > best[ssid]["signal"]:
            best[ssid] = {"ssid": ssid, "signal": signal, "secure": security not in ("", "--")}
    return sorted(best.values(), key=lambda r: -r["signal"])


def scan(run=nmcli, rescan=True):
    """Visible networks, strongest first. While the setup hotspot is up the radio
    can't scan, so fall back to the list netwatch saved just before starting it."""
    try:
        out = run("-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                  "--rescan", "yes" if rescan else "no")
        nets = _parse_scan(out)
        if nets:
            return nets
    except WifiError:
        pass
    try:
        with open(SCAN_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def save_scan(run=nmcli, path=SCAN_FILE):
    nets = scan(run)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(nets, fh)
    return nets


def add(ssid, password, priority=0, run=nmcli):
    ssid = ssid.strip()
    if not ssid:
        raise WifiError("network name is empty")
    if password and not 8 <= len(password) <= 63:
        raise WifiError("WiFi passwords are 8 to 63 characters")
    for row in saved(run):
        if row["ssid"] == ssid:
            run("connection", "delete", row["name"])
    args = ["connection", "add", "type", "wifi", "ifname", IFACE, "con-name", ssid,
            "ssid", ssid, "connection.autoconnect", "yes",
            "connection.autoconnect-priority", str(int(priority))]
    if password:
        args += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
    run(*args)


def remove(name, run=nmcli):
    run("connection", "delete", name)


def set_priority(name, priority, run=nmcli):
    run("connection", "modify", name, "connection.autoconnect-priority", str(int(priority)))


def connect_later(name, delay=3, run=nmcli):
    """Switch to `name` after the HTTP response has gone out: if the phone is on
    the setup hotspot, switching drops it, and it should see the reply first."""
    def go():
        time.sleep(delay)
        try:
            run("connection", "up", name, timeout=60)
        except WifiError:
            pass  # netwatch brings the hotspot back if this fails
    threading.Thread(target=go, daemon=True).start()
