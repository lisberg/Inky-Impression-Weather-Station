"""Synthetic provider payloads in the shape the real APIs return."""
import math
from datetime import datetime, timedelta, timezone

START = datetime(2026, 10, 19, 14, tzinfo=timezone.utc)
YR_SYMBOLS = ["partlycloudy_day", "cloudy", "lightrain", "rain", "heavyrainshowers_day",
              "clearsky_day", "fair_day", "snow", "fog", "rainshowersandthunder_day"]


def _times():
    t, out = START, []
    while t < START + timedelta(hours=60):
        out.append(t)
        t += timedelta(hours=1)
    t = t.replace(hour=(t.hour // 6) * 6) + timedelta(hours=6)
    while t < START + timedelta(days=9):
        out.append(t)
        t += timedelta(hours=6)
    return out


def temp_at(t):
    hours = (t - START).total_seconds() / 3600
    return 8 + 5 * math.sin((t.hour - 9) / 24 * 2 * math.pi) - hours / 40


def yr_payload():
    series = []
    for i, t in enumerate(_times()):
        sym = YR_SYMBOLS[(i // 7) % len(YR_SYMBOLS)]
        data = {"instant": {"details": {"air_temperature": round(temp_at(t), 1), "wind_speed": 4.2,
                                        "wind_from_direction": 220}},
                "next_6_hours": {"summary": {"symbol_code": sym},
                                 "details": {"precipitation_amount": 1.2 if "rain" in sym else 0.0}}}
        if (t - START) < timedelta(hours=60):
            data["next_1_hours"] = {"summary": {"symbol_code": sym},
                                    "details": {"precipitation_amount": 0.3 if "rain" in sym else 0.0}}
        series.append({"time": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "data": data})
    return {"type": "Feature", "properties": {"meta": {}, "timeseries": series}}


def smhi_pmp3g_payload():
    series = []
    for i, t in enumerate(_times()):
        series.append({"validTime": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "parameters": [
            {"name": "t", "levelType": "hl", "level": 2, "unit": "Cel", "values": [round(temp_at(t), 1)]},
            {"name": "ws", "levelType": "hl", "level": 10, "unit": "m/s", "values": [3.0]},
            {"name": "wd", "levelType": "hl", "level": 10, "unit": "degree", "values": [180]},
            {"name": "pmean", "levelType": "hl", "level": 0, "unit": "kg/m2/h", "values": [0.5 if i % 5 == 0 else 0.0]},
            {"name": "Wsymb2", "levelType": "hl", "level": 0, "unit": "category", "values": [(i % 27) + 1]},
        ]})
    return {"approvedTime": "2026-10-19T13:00:00Z", "timeSeries": series}


def smhi_snow1g_payload():
    series, prev = [], None
    for i, t in enumerate(_times()):
        entry = {"time": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "data": {"air_temperature": round(temp_at(t), 1), "wind_speed": 3.0,
                          "wind_from_direction": 180, "symbol_code": (i % 27) + 1,
                          "precipitation_amount_mean": 0.5 if i % 5 == 0 else 0.0}}
        if prev:
            entry["intervalParametersStartTime"] = prev.strftime("%Y-%m-%dT%H:%M:%SZ")
        series.append(entry)
        prev = t
    return {"createdTime": "2026-10-19T13:00:00Z", "timeSeries": series}
