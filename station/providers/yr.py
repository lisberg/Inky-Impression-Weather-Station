"""MET Norway / Yr locationforecast 2.0.

https://api.met.no/weatherapi/locationforecast/2.0/documentation
Terms: identify yourself in User-Agent, cache until Expires, max 4 decimals.
"""
from datetime import timedelta

from ..models import Point
from .base import fetch_json, make_forecast, parse_time

URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={lat:.4f}&lon={lon:.4f}"
NAME = "yr"


def parse(data):
    series = data["properties"]["timeseries"]
    times = [parse_time(e["time"]) for e in series]
    points = []
    for i, entry in enumerate(series):
        t = times[i]
        d = entry["data"]
        inst = d["instant"]["details"]
        n1, n6 = d.get("next_1_hours"), d.get("next_6_hours")
        gap = (times[i + 1] - t) if i + 1 < len(series) else timedelta(hours=1 if n1 else 6)
        gap_h = gap.total_seconds() / 3600
        symbol, precip = None, 0.0
        if n1 and gap_h <= 1:
            symbol = n1["summary"]["symbol_code"]
            precip = n1["details"].get("precipitation_amount", 0.0)
        elif n6:
            symbol = n6["summary"]["symbol_code"]
            precip = n6["details"].get("precipitation_amount", 0.0) * min(gap_h, 6) / 6
        elif n1:
            symbol = n1["summary"]["symbol_code"]
        points.append(Point(
            time=t, temp=inst.get("air_temperature"), symbol=symbol,
            wind_speed=inst.get("wind_speed"), wind_dir=inst.get("wind_from_direction"),
            precip_mm=precip, precip_from=t, precip_to=t + gap,
            symbol_6h=n6["summary"]["symbol_code"] if n6 else None))
    return points


def get_forecast(location, tz, contact=""):
    data, stale = fetch_json(URL.format(lat=location["lat"], lon=location["lon"]), contact)
    return make_forecast(location, NAME, parse(data), stale, tz)
