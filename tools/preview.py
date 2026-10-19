#!/usr/bin/env python3
"""Render every layout/theme from sample data into docs/, no network or panel needed."""
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from station import render  # noqa: E402
from station.providers import base, yr  # noqa: E402
from tests import samples  # noqa: E402

tz = ZoneInfo("Europe/Stockholm")
loc = {"name": "Stockholm", "lat": 59.3293, "lon": 18.0686, "provider": "yr"}
fc = base.make_forecast(loc, "yr", yr.parse(samples.yr_payload()), False, tz)
for layout in render.LAYOUTS:
    for night, hour in ((False, 15), (True, 21)):
        now = datetime(2026, 10, 19, hour, 45, tzinfo=tz)
        img = render.render(fc, loc, now, tz, layout=layout, night=night)
        out = os.path.join(ROOT, "docs", "preview-%s-%s.png" % (layout, "night" if night else "day"))
        img.save(out)
        print(out)
