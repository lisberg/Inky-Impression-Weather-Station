"""The station's main loop: fetch, render, push to the panel, sleep."""
import argparse
import logging
import threading
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from . import __version__, buttons, netinfo
from . import config as cfgmod
from .display import open_display
from .providers import ProviderError, get_forecast
from .render import LAYOUTS, render, render_info, render_setup
from .sun import is_daylight

log = logging.getLogger("station")


def _parse_hhmm(s):
    try:
        h, m = s.split(":")
        return dtime(int(h), int(m))
    except (AttributeError, ValueError):
        return None


def in_quiet_hours(cfg, now):
    start = _parse_hhmm(cfg["quiet_hours"].get("start"))
    end = _parse_hhmm(cfg["quiet_hours"].get("end"))
    if not start or not end or start == end:
        return False
    t = now.time()
    return start <= t < end if start < end else (t >= start or t < end)


def use_night_theme(cfg, location, now):
    mode = cfg["night_mode"]
    if mode == "on":
        return True
    if mode == "off":
        return False
    return not is_daylight(now, location["lat"], location["lon"])


SETTLE = 1.5     # wait for more presses before a redraw, so A-A-A skips two places
CHECK_EVERY = 60  # how often to look for hotspot changes between redraws


class Station:
    def __init__(self, config_path=cfgmod.DEFAULT_PATH, display=None):
        self.config_path = config_path
        self.display = display or open_display()
        self.wake = threading.Event()   # set by buttons or the dashboard to redraw now
        self.forecasts = {}             # last good forecast per location
        self.showing_info = False
        self._actions = []
        self._lock = threading.Lock()

    def load_config(self):
        return cfgmod.load(self.config_path)

    # --- input --------------------------------------------------------------
    def press(self, action):
        with self._lock:
            self._actions.append(action)
        self.wake.set()

    def apply_actions(self, cfg):
        with self._lock:
            actions, self._actions = self._actions, []
        if not actions:
            return cfg
        changed = False
        for action in actions:
            self.showing_info = action == "info"
            n = len(cfg["locations"])
            if action in ("next_location", "previous_location"):
                step = 1 if action == "next_location" else -1
                cfg["active_location"] = (cfg["active_location"] + step) % n
                changed = True
            elif action == "next_layout":
                names = list(LAYOUTS)
                cfg["layout"] = names[(names.index(cfg["layout"]) + 1) % len(names)]
                changed = True
        if changed:
            cfg = cfgmod.save(cfg, self.config_path)
            log.info("now showing %s (%s)", cfgmod.active_location(cfg)["name"], cfg["layout"])
        return cfg

    # --- drawing ------------------------------------------------------------
    def frame(self, cfg, now=None, hotspot=None):
        loc = cfgmod.active_location(cfg)
        tz = ZoneInfo(loc.get("timezone") or cfg["timezone"])
        now = (now or datetime.now(tz)).astimezone(tz)
        if hotspot:
            return render_setup(hotspot, cfg)
        if self.showing_info:
            return render_info(netinfo.summary(), cfg, now, __version__)
        key = (loc["name"], loc["lat"], loc["lon"], loc["provider"])
        error = None
        try:
            self.forecasts[key] = get_forecast(loc, tz, cfg.get("contact", ""))
        except ProviderError as exc:
            log.error("forecast failed for %s: %s", loc["name"], exc)
            error = str(exc)
        forecast = self.forecasts.get(key)
        return render(forecast, loc, now, tz, lang=cfg["language"], layout=cfg["layout"],
                      night=use_night_theme(cfg, loc, now),
                      error=error if forecast is None else None)

    def refresh(self, cfg=None, hotspot=None):
        cfg = cfg or self.load_config()
        img = self.frame(cfg, hotspot=hotspot)
        self.display.show(img, rotate=cfg["display"]["rotate"],
                          saturation=cfg["display"]["saturation"])
        return img

    def run(self):
        next_due = 0.0
        last_hotspot = None
        while True:
            forced = self.wake.is_set()
            if forced:
                time.sleep(SETTLE)
                self.wake.clear()
            cfg = self.apply_actions(self.load_config())
            tz = ZoneInfo(cfg["timezone"])
            now = datetime.now(tz)
            hotspot = netinfo.hotspot()
            due = time.time() >= next_due
            if forced or hotspot != last_hotspot or (due and not in_quiet_hours(cfg, now)):
                try:
                    self.refresh(cfg, hotspot)
                except Exception:  # never let one bad frame kill the service
                    log.exception("refresh failed")
                last_hotspot = hotspot
            if due or forced:
                # next redraw on the next whole interval (…:00, :15, :30, :45)
                step = int(cfg["refresh_minutes"]) * 60
                next_due = time.time() + step - (now.minute * 60 + now.second) % step
            self.wake.wait(timeout=max(1, min(CHECK_EVERY, next_due - time.time())))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inky Impression weather station")
    ap.add_argument("--config", default=cfgmod.DEFAULT_PATH)
    ap.add_argument("--once", action="store_true", help="draw one frame and exit")
    ap.add_argument("--preview", metavar="PNG", help="write to a PNG instead of the panel")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    station = Station(args.config, open_display(args.preview))
    if args.once or args.preview:
        station.refresh(hotspot=netinfo.hotspot())
        return
    cfg = station.load_config()
    held = buttons.attach(station, cfg["buttons"]["pins"]) if cfg["buttons"]["enabled"] else []
    try:
        station.run()
    finally:
        for b in held:
            b.close()


if __name__ == "__main__":
    main()
