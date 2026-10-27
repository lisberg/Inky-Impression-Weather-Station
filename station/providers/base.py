import hashlib
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .. import __version__
from ..config import STATE_DIR
from ..models import Day, Forecast

log = logging.getLogger(__name__)

USER_AGENT = "InkyWeatherStation/%s github.com/lisberg/Inky-Impression-Weather-Station" % __version__
MIN_CACHE_SECONDS = 10 * 60


class ProviderError(RuntimeError):
    pass


def _cache_path(url):
    return os.path.join(STATE_DIR, "cache", hashlib.sha1(url.encode()).hexdigest() + ".json")


def fetch_json(url, contact="", session=None):
    """GET `url` as JSON, honouring the server's Expires header.

    Returns (data, stale). A fresh cache entry is used without touching the
    network; a failed request falls back to the last good copy with stale=True,
    so a WiFi hiccup shows old data instead of an error screen.
    """
    path = _cache_path(url)
    cached = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cached = json.load(fh)
        except (OSError, ValueError):
            cached = None
    if cached and cached.get("expires", 0) > time.time():
        return cached["data"], False

    if contact.strip().lower().endswith("example.com"):
        contact = ""  # MET Norway answers 403 to the placeholder address
    headers = {"User-Agent": USER_AGENT + ((" " + contact.strip()) if contact else "")}
    if cached and cached.get("last_modified"):
        headers["If-Modified-Since"] = cached["last_modified"]
    try:
        resp = (session or requests).get(url, headers=headers, timeout=20)
        if resp.status_code == 304 and cached:
            data = cached["data"]
        else:
            resp.raise_for_status()
            data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        if cached:
            log.warning("fetch failed (%s), using cached data", exc)
            return cached["data"], True
        raise ProviderError(str(exc)) from exc

    expires = time.time() + MIN_CACHE_SECONDS
    if resp.headers.get("Expires"):
        try:
            expires = max(expires, parsedate_to_datetime(resp.headers["Expires"]).timestamp())
        except (TypeError, ValueError):
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"expires": expires, "last_modified": resp.headers.get("Last-Modified"),
                   "data": data}, fh)
    os.replace(tmp, path)
    return data, False


def base_symbol(symbol):
    return symbol.split("_")[0] if symbol else None


def build_days(points, tz, count=8):
    """Aggregate a point series into local calendar days."""
    temps = defaultdict(list)
    winds = defaultdict(list)
    precip = defaultdict(float)
    symbols = defaultdict(list)
    for p in points:
        local = p.time.astimezone(tz)
        d = local.date()
        if p.temp is not None:
            temps[d].append(p.temp)
        if p.wind_speed is not None:
            winds[d].append(p.wind_speed)
        if p.precip_mm and p.precip_from and p.precip_to:
            mid = p.precip_from + (p.precip_to - p.precip_from) / 2
            precip[mid.astimezone(tz).date()] += p.precip_mm
        sym = p.symbol_6h or p.symbol
        if sym:
            # weight towards the daytime: the symbol nearest 13:00 local wins
            symbols[d].append((abs(local.hour + local.minute / 60 - 13), sym))
    days = []
    for d in sorted(temps):
        sym = min(symbols[d])[1] if symbols[d] else None
        days.append(Day(date=d, tmin=min(temps[d]), tmax=max(temps[d]),
                        precip_mm=round(precip[d], 1), symbol=base_symbol(sym),
                        wind_max=max(winds[d]) if winds[d] else None))
    return days[:count]


def make_forecast(location, provider, points, stale, tz):
    points = sorted(points, key=lambda p: p.time)
    return Forecast(location=location["name"], provider=provider,
                    fetched=datetime.now(timezone.utc), points=points,
                    days=build_days(points, tz), stale=stale)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hours(td: timedelta):
    return td.total_seconds() / 3600
