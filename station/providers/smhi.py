"""SMHI open data point forecast (Nordic area only).

Tries the current snow1g API first and falls back to the older pmp3g one, so
the station keeps working whichever of the two SMHI is serving.
https://opendata.smhi.se/metfcst/
"""
from datetime import timedelta

from ..models import Point
from ..sun import is_daylight
from .base import ProviderError, fetch_json, make_forecast, parse_time

NAME = "smhi"
BASE = "https://opendata-download-metfcst.smhi.se/api/category/"
URLS = (
    BASE + "snow1g/version/1/geotype/point/lon/{lon:.4f}/lat/{lat:.4f}/data.json",
    BASE + "pmp3g/version/2/geotype/point/lon/{lon:.4f}/lat/{lat:.4f}/data.json",
)

# SMHI weather symbol (Wsymb2, 1-27) -> Yr symbol base code
WSYMB2 = {
    1: "clearsky", 2: "fair", 3: "partlycloudy", 4: "partlycloudy",
    5: "cloudy", 6: "cloudy", 7: "fog",
    8: "lightrainshowers", 9: "rainshowers", 10: "heavyrainshowers",
    11: "rainshowersandthunder",
    12: "lightsleetshowers", 13: "sleetshowers", 14: "heavysleetshowers",
    15: "lightsnowshowers", 16: "snowshowers", 17: "heavysnowshowers",
    18: "lightrain", 19: "rain", 20: "heavyrain", 21: "rainandthunder",
    22: "lightsleet", 23: "sleet", 24: "heavysleet",
    25: "lightsnow", 26: "snow", 27: "heavysnow",
}
# Yr only gives these a day/night variant
_HAS_VARIANT = ("clearsky", "fair", "partlycloudy")


def _with_variant(base, daylight):
    if base and (base in _HAS_VARIANT or base.endswith("showers") or base.endswith("showersandthunder")):
        return base + ("_day" if daylight else "_night")
    return base


def _values(entry):
    """Flatten one time step of either API version into {name: value}."""
    if "parameters" in entry:  # pmp3g
        return {p["name"]: p["values"][0] for p in entry["parameters"]}
    return dict(entry.get("data", {}))  # snow1g


def _first(values, *names):
    for name in names:
        v = values.get(name)
        if v is not None and v != 9999:
            return v
    return None


def parse(data, lat, lon):
    series = data["timeSeries"]
    points = []
    prev = None
    for entry in series:
        t = parse_time(entry.get("validTime") or entry["time"])
        v = _values(entry)
        start = entry.get("intervalParametersStartTime")
        start = parse_time(start) if start else (prev or t - timedelta(hours=1))
        span_h = max((t - start).total_seconds() / 3600, 0)
        if "pmean" in v:  # mm/h over the preceding step
            precip = max(v["pmean"], 0) * span_h
        else:
            precip = max(_first(v, "precipitation_amount_mean", "precipitation_amount") or 0, 0)
        sym = _first(v, "Wsymb2", "symbol_code")
        base = WSYMB2.get(int(sym)) if sym is not None else None
        points.append(Point(
            time=t, temp=_first(v, "t", "air_temperature"),
            symbol=_with_variant(base, is_daylight(t, lat, lon)),
            wind_speed=_first(v, "ws", "wind_speed"),
            wind_dir=_first(v, "wd", "wind_from_direction"),
            precip_mm=precip, precip_from=start, precip_to=t))
        prev = t
    return points


def get_forecast(location, tz, contact=""):
    last = None
    for url in URLS:
        try:
            data, stale = fetch_json(url.format(lat=location["lat"], lon=location["lon"]), contact)
            return make_forecast(location, NAME,
                                 parse(data, location["lat"], location["lon"]), stale, tz)
        except (ProviderError, KeyError) as exc:
            last = exc
    raise ProviderError("SMHI: %s" % last)
