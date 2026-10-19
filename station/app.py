"""The station's main loop: fetch, render, push to the panel, sleep."""
import argparse
import logging
import threading
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from . import config as cfgmod
from .display import open_display
from .providers import ProviderError, get_forecast
from .render import render
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


class Station:
    def __init__(self, config_path=cfgmod.DEFAULT_PATH, display=None):
        self.config_path = config_path
        self.display = display or open_display()
        self.wake = threading.Event()   # set by buttons or the dashboard to redraw now
        self.forecasts = {}             # last good forecast per location index

    def load_config(self):
        return cfgmod.load(self.config_path)

    def frame(self, cfg, now=None):
        loc = cfgmod.active_location(cfg)
        tz = ZoneInfo(loc.get("timezone") or cfg["timezone"])
        now = (now or datetime.now(tz)).astimezone(tz)
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

    def refresh(self, cfg=None):
        cfg = cfg or self.load_config()
        img = self.frame(cfg)
        self.display.show(img, rotate=cfg["display"]["rotate"],
                          saturation=cfg["display"]["saturation"])
        return img

    def run(self):
        while True:
            cfg = self.load_config()
            tz = ZoneInfo(cfg["timezone"])
            now = datetime.now(tz)
            forced = self.wake.is_set()
            self.wake.clear()
            if forced or not in_quiet_hours(cfg, now):
                try:
                    self.refresh(cfg)
                except Exception:  # never let one bad frame kill the service
                    log.exception("refresh failed")
            # Sleep until the next whole interval (…:00, :15, :30, :45) or a wake-up.
            step = int(cfg["refresh_minutes"]) * 60
            secs = step - (now.minute * 60 + now.second) % step
            self.wake.wait(timeout=max(secs, 30))


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
        station.refresh()
    else:
        station.run()


if __name__ == "__main__":
    main()
