import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from station import config, render, symbols
from station.providers import base, smhi, yr
from station.sun import is_daylight, sun_times_local
from tests import samples

TZ = ZoneInfo("Europe/Stockholm")
LOC = {"name": "Stockholm", "lat": 59.3293, "lon": 18.0686, "provider": "yr"}


def test_sun_times_stockholm():
    rise, sset, state = sun_times_local(date(2026, 10, 19), LOC["lat"], LOC["lon"], TZ)
    assert state == "normal"
    # reference values from the astral library: 07:35 / 17:29
    assert abs((rise.hour * 60 + rise.minute) - (7 * 60 + 35)) <= 2
    assert abs((sset.hour * 60 + sset.minute) - (17 * 60 + 29)) <= 2


def test_polar_states():
    _, _, summer = sun_times_local(date(2026, 6, 21), 68.35, 18.83, ZoneInfo("Europe/Stockholm"))
    _, _, winter = sun_times_local(date(2026, 12, 21), 69.0, 18.83, ZoneInfo("Europe/Stockholm"))
    assert (summer, winter) == ("midnight_sun", "polar_night")


def test_daylight():
    assert is_daylight(datetime(2026, 10, 19, 10, tzinfo=timezone.utc), LOC["lat"], LOC["lon"])
    assert not is_daylight(datetime(2026, 10, 19, 20, tzinfo=timezone.utc), LOC["lat"], LOC["lon"])


def test_yr_parse_and_days():
    points = yr.parse(samples.yr_payload())
    days = base.build_days(points, TZ)
    assert len(days) == 8 and days[0].date == date(2026, 10, 19)
    assert all(d.tmin <= d.tmax for d in days)
    # hourly section uses next_1_hours, 6-hourly section next_6_hours: no double counting
    last = days[-1].date
    total = sum(p.precip_mm for p in points if p.precip_from.astimezone(TZ).date() <= last)
    assert total == pytest.approx(sum(d.precip_mm for d in days), abs=0.5)
    assert all(d.symbol and "_" not in d.symbol for d in days)


@pytest.mark.parametrize("payload", [samples.smhi_pmp3g_payload, samples.smhi_snow1g_payload])
def test_smhi_parse(payload):
    points = smhi.parse(payload(), LOC["lat"], LOC["lon"])
    assert points[0].temp is not None and points[0].symbol
    days = base.build_days(points, TZ)
    assert len(days) == 8
    assert sum(d.precip_mm for d in days) > 0


def test_every_symbol_has_a_glyph():
    codes = set(smhi.WSYMB2.values()) | {s.split("_")[0] for s in samples.YR_SYMBOLS}
    for code in codes:
        for night in (False, True):
            name, role = symbols.icon_for(code, night)
            assert name != "na", code
            assert name in render.GLYPHS, name
    for name in ("sunrise", "sunset", "strong-wind", "cloud-refresh", "na"):
        assert name in render.GLYPHS


def test_config_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = config.load(str(path))
    cfg["locations"].append({"name": "Kiruna", "lat": "67.85", "lon": 20.22, "provider": "smhi"})
    cfg["active_location"] = 1
    config.save(cfg, str(path))
    again = config.load(str(path))
    assert again["locations"][1]["lat"] == 67.85 and again["active_location"] == 1
    assert json.loads(path.read_text())["layout"] == "overview"


@pytest.mark.parametrize("bad", [
    {"locations": []},
    {"locations": [{"name": "X", "lat": 99, "lon": 0}]},
    {"layout": "nope"},
    {"refresh_minutes": 1},
])
def test_config_rejects(bad, tmp_path):
    with pytest.raises(config.ConfigError):
        config.validate(config._merge(config.DEFAULTS, bad))


@pytest.mark.parametrize("layout", render.LAYOUTS)
@pytest.mark.parametrize("night", [False, True])
@pytest.mark.parametrize("lang", ["sv", "en"])
def test_render(layout, night, lang):
    fc = base.make_forecast(LOC, "yr", yr.parse(samples.yr_payload()), False, TZ)
    now = datetime(2026, 10, 19, 16, 45, tzinfo=TZ)
    img = render.render(fc, LOC, now, TZ, lang=lang, layout=layout, night=night)
    assert img.size == (800, 480)
    # only pure panel inks: nothing for the driver to dither
    assert {c for _, c in img.getcolors(64)} <= set(render.INK.values())


def test_render_without_data():
    img = render.render(None, LOC, datetime(2026, 10, 19, 16, tzinfo=TZ), TZ, error="boom")
    assert img.size == (800, 480)
