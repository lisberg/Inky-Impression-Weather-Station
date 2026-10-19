"""Keep the station reachable: fall back to a setup hotspot when WiFi is gone.

Runs as its own root service (NetworkManager changes need root). When no saved
network has connected for GRACE seconds, it brings up an access point. The
screen then tells the user to join it and open the dashboard to pick a
network. With nobody connected, the hotspot is dropped every HOTSPOT_WINDOW
seconds so NetworkManager can retry the saved networks. That way a router
that was only rebooting gets picked up again on its own.
"""
import json
import logging
import os
import subprocess
import time

from . import config as cfgmod
from .netinfo import HOTSPOT_FILE

log = logging.getLogger("netwatch")

IFACE = "wlan0"
CON_NAME = "station-setup"
GRACE = 120
HOTSPOT_WINDOW = 10 * 60
POLL = 15
X


def nmcli(*args, check=True):
    out = subprocess.run(("nmcli",) + args, capture_output=True, text=True, timeout=30)
    if check and out.returncode:
        raise RuntimeError("nmcli %s: %s" % (" ".join(args), out.stderr.strip()))
    return out.stdout


class NetWatch:
    def __init__(self, run=nmcli, clock=time.monotonic, hotspot_file=HOTSPOT_FILE):
        self.run = run
        self.clock = clock
        self.hotspot_file = hotspot_file
        self.offline_since = None
        self.hotspot_since = None

    # --- NetworkManager queries -------------------------------------------
    def wifi_state(self):
        """Return (state, connection) of the WiFi interface, e.g. ("connected", "Home")."""
        for line in self.run("-t", "-f", "DEVICE,STATE,CONNECTION", "device").splitlines():
            dev, state, con = (line.split(":", 2) + ["", ""])[:3]
            if dev == IFACE:
                return state, con
        return "unavailable", ""

    def hotspot_clients(self):
        try:
            out = subprocess.run(("iw", "dev", IFACE, "station", "dump"),
                                 capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return 0
        return out.count("Station ")

    # --- hotspot ----------------------------------------------------------
    def start_hotspot(self, ssid, password):
        self.run("connection", "delete", CON_NAME, check=False)
        self.run("connection", "add", "type", "wifi", "ifname", IFACE, "con-name", CON_NAME,
                 "autoconnect", "no", "ssid", ssid, "mode", "ap", "ipv4.method", "shared",
                 "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password)
        self.run("connection", "up", CON_NAME)
        self.hotspot_since = self.clock()
        self._write_state({"ssid": ssid, "password": password, "url": HOTSPOT_URL})
        log.warning("no WiFi for %ds, started setup hotspot %r", GRACE, ssid)

    def stop_hotspot(self):
        self.run("connection", "down", CON_NAME, check=False)
        self.hotspot_since = None
        self._write_state(None)
        log.info("setup hotspot stopped, letting NetworkManager retry saved networks")

    def _write_state(self, data):
        if data is None:
            try:
                os.remove(self.hotspot_file)
            except FileNotFoundError:
                pass
            return
        os.makedirs(os.path.dirname(self.hotspot_file), exist_ok=True)
        tmp = self.hotspot_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, self.hotspot_file)

    # --- policy -----------------------------------------------------------
    def step(self, ssid, password):
        now = self.clock()
        state, con = self.wifi_state()
        if self.hotspot_since is not None:
            if con != CON_NAME:  # the user picked a network and NM switched to it
                self.hotspot_since = None
                self._write_state(None)
            elif now - self.hotspot_since > HOTSPOT_WINDOW and not self.hotspot_clients():
                self.stop_hotspot()
                self.offline_since = now
            return
        if state == "connected":
            self.offline_since = None
            return
        if self.offline_since is None:
            self.offline_since = now
        elif now - self.offline_since > GRACE:
            self.start_hotspot(ssid, password)

    def run_forever(self):
        self._write_state(None)
        while True:
            cfg = cfgmod.load()
            hs = cfg["setup_hotspot"]
            try:
                self.step(hs["ssid"], hs["password"])
            except Exception:
                log.exception("netwatch step failed")
            time.sleep(POLL)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    NetWatch().run_forever()


if __name__ == "__main__":
    main()
