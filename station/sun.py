"""Sunrise and sunset from the NOAA solar position equations.

Accurate to about a minute, which is plenty for an e-ink screen and saves a
network call and a dependency.
"""
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

ZENITH = 90.833  # geometric zenith incl. refraction and solar disc radius


def _julian_day(d: date) -> float:
    return d.toordinal() + 1721424.5


def _event(d: date, lat: float, lon: float, rising: bool) -> Tuple[Optional[datetime], str]:
    jd = _julian_day(d) + 0.5 - lon / 360.0
    t = (jd - 2451545.0) / 36525.0
    for _ in range(3):  # iterate so declination is taken near the event itself
        l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360
        m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
        e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
        mr = math.radians(m)
        c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
             + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
             + math.sin(3 * mr) * 0.000289)
        omega = 125.04 - 1934.136 * t
        app_long = l0 + c - 0.00569 - 0.00478 * math.sin(math.radians(omega))
        eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
        eps = eps0 + 0.00256 * math.cos(math.radians(omega))
        decl = math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long)))
        y = math.tan(math.radians(eps / 2)) ** 2
        l0r = math.radians(l0)
        eq_time = 4 * math.degrees(
            y * math.sin(2 * l0r) - 2 * e * math.sin(mr)
            + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
            - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
        latr = math.radians(lat)
        cos_ha = (math.cos(math.radians(ZENITH)) / (math.cos(latr) * math.cos(decl))
                  - math.tan(latr) * math.tan(decl))
        if cos_ha > 1:
            return None, "polar_night"
        if cos_ha < -1:
            return None, "midnight_sun"
        ha = math.degrees(math.acos(cos_ha))
        minutes = 720 - 4 * (lon + (ha if rising else -ha)) - eq_time
        t = (_julian_day(d) + minutes / 1440.0 - 2451545.0) / 36525.0
    midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return midnight + timedelta(minutes=minutes), "normal"


def sun_times(d: date, lat: float, lon: float):
    """Return (sunrise, sunset, state) in UTC for the UTC calendar day `d`.

    state is "normal", "midnight_sun" or "polar_night"; in the latter two the
    times are None.
    """
    rise, state = _event(d, lat, lon, True)
    sset, _ = _event(d, lat, lon, False)
    return rise, sset, state


def sun_times_local(d: date, lat: float, lon: float, tz):
    """Sunrise/sunset for the local calendar day `d`, as local datetimes."""
    noon_utc = datetime(d.year, d.month, d.day, 12, tzinfo=tz).astimezone(timezone.utc)
    rise, sset, state = sun_times(noon_utc.date(), lat, lon)
    if state != "normal":
        return None, None, state
    return rise.astimezone(tz), sset.astimezone(tz), state


def is_daylight(when: datetime, lat: float, lon: float) -> bool:
    rise, sset, state = sun_times(when.astimezone(timezone.utc).date(), lat, lon)
    if state == "midnight_sun":
        return True
    if state == "polar_night":
        return False
    return rise <= when <= sset
