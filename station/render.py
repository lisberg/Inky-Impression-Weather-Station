"""Draw the forecast as an 800x480 image for the Inky Impression 7.3".

Everything is drawn in the panel's pure inks with antialiasing off, so the
driver never has to dither text edges into coloured noise.
"""
import json
import os
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from .i18n import t as strings
from .sun import is_daylight, sun_times_local
from .symbols import icon_for

WIDTH, HEIGHT = 800, 480
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONTS = os.path.join(ASSETS, "fonts")

INK = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
    "green": (0, 255, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
}

THEMES = {
    "day": {"bg": "white", "fg": "black", "rule": "black", "tmax": "red", "tmin": "blue",
            "weekend": "red", "warn": "red",
            "sun": "red", "rain": "blue", "snow": "blue", "thunder": "red", "cloud": "black"},
    "night": {"bg": "black", "fg": "white", "rule": "white", "tmax": "yellow", "tmin": "white",
              "weekend": "yellow", "warn": "yellow",
              "sun": "yellow", "rain": "white", "snow": "white", "thunder": "yellow", "cloud": "white"},
}

with open(os.path.join(ASSETS, "weathericons.json"), encoding="utf-8") as _fh:
    GLYPHS = json.load(_fh)

_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        name = "AtkinsonHyperlegible-Bold.ttf" if bold else "AtkinsonHyperlegible-Regular.ttf"
        _font_cache[key] = ImageFont.truetype(os.path.join(FONTS, name), size)
    return _font_cache[key]


def icon_font(size):
    key = ("icon", size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONTS, "weathericons-regular-webfont.ttf"), size)
    return _font_cache[key]


class Canvas:
    def __init__(self, theme):
        self.theme = THEMES[theme]
        self.img = Image.new("RGB", (WIDTH, HEIGHT), INK[self.theme["bg"]])
        self.draw = ImageDraw.Draw(self.img)
        self.draw.fontmode = "1"

    def ink(self, role):
        return INK[self.theme.get(role, role)]

    def text(self, xy, s, size, role="fg", bold=False, anchor="la"):
        self.draw.text(xy, s, fill=self.ink(role), font=font(size, bold), anchor=anchor)

    def width(self, s, size, bold=False):
        return self.draw.textlength(s, font=font(size, bold))

    def icon(self, center, name, size, role="fg"):
        glyph = chr(int(GLYPHS.get(name, GLYPHS["na"]), 16))
        f = icon_font(size)
        x0, y0, x1, y1 = self.draw.textbbox((0, 0), glyph, font=f)
        cx, cy = center
        self.draw.text((cx - (x0 + x1) / 2, cy - (y0 + y1) / 2), glyph, fill=self.ink(role), font=f)

    def weather_icon(self, center, symbol, size, night=None):
        name, role = icon_for(symbol, night)
        self.icon(center, name, size, role)

    def hline(self, y, x0=0, x1=WIDTH, width=2):
        self.draw.line((x0, y, x1, y), fill=self.ink("rule"), width=width)

    def vline(self, x, y0, y1, width=1):
        self.draw.line((x, y0, x, y1), fill=self.ink("rule"), width=width)


def _deg(v):
    return "–" if v is None else "%d°" % round(v)


def _mm(v):
    if not v or v < 0.05:
        return ""
    return ("%.1f mm" % v) if v < 10 else ("%d mm" % round(v))


def _day_name(d, lang, today):
    s = strings(lang)
    if d == today:
        return s["today"]
    return s["days"][d.weekday()]


def _header(c, location, now, lang, forecast, error):
    s = strings(lang)
    c.text((16, 34), location["name"], 40, bold=True, anchor="lm")
    stamp = "%s %d %s  %s" % (s["days"][now.weekday()], now.day, s["months"][now.month - 1],
                              now.strftime("%H:%M"))
    c.text((WIDTH - 16, 34), stamp, 34, bold=True, anchor="rm")
    if error:
        c.text((WIDTH // 2, 62), s["error"], 18, role="warn", anchor="ms")
    elif forecast and forecast.stale:
        c.text((WIDTH // 2, 62), s["offline"], 18, role="warn", anchor="ms")
    c.hline(70)


def _sun_row(c, xy, location, now, tz, lang):
    rise, sset, state = sun_times_local(now.date(), location["lat"], location["lon"], tz)
    x, y = xy
    if state != "normal":
        c.icon((x + 18, y), "day-sunny" if state == "midnight_sun" else "night-clear", 30, "sun")
        c.text((x + 44, y), strings(lang)[state], 26, anchor="lm")
        return
    c.icon((x + 20, y - 2), "sunrise", 34, "sun")
    c.text((x + 50, y), rise.strftime("%H:%M"), 26, bold=True, anchor="lm")
    c.icon((x + 170, y - 2), "sunset", 34, "sun")
    c.text((x + 200, y), sset.strftime("%H:%M"), 26, bold=True, anchor="lm")


def _current_point(forecast, now):
    best = None
    for p in forecast.points:
        if p.time <= now.astimezone(timezone.utc) + timedelta(minutes=30):
            best = p
        else:
            break
    return best or forecast.points[0]


def _days_from(forecast, today, n):
    return [d for d in forecast.days if d.date >= today][:n]


def layout_overview(c, forecast, location, now, tz, lang, night):
    cur = _current_point(forecast, now)
    # Now panel
    dark = lambda when: not is_daylight(when, location["lat"], location["lon"])  # noqa: E731
    c.weather_icon((80, 155), cur.symbol, 96, dark(now))
    c.text((250, 160), _deg(cur.temp), 96, bold=True, anchor="mm")
    today = now.date()
    td = next((d for d in forecast.days if d.date == today), None)
    y = 255
    if td:
        c.text((24, y), _deg(td.tmax), 30, role="tmax", bold=True, anchor="lm")
        c.text((24 + c.width(_deg(td.tmax), 30, True) + 10, y), _deg(td.tmin), 30,
               role="tmin", bold=True, anchor="lm")
    if cur.wind_speed is not None:
        c.icon((190, y), "strong-wind", 28, "fg")
        c.text((214, y), "%d m/s" % round(cur.wind_speed), 26, anchor="lm")
    _sun_row(c, (12, 298), location, now, tz, lang)
    c.vline(345, 80, 320)

    # Next hours, every second hour
    utc_now = now.astimezone(timezone.utc)
    upcoming = [p for p in forecast.points if p.time > utc_now - timedelta(minutes=30)]
    hourly = [p for p in upcoming if (p.precip_to - p.precip_from) <= timedelta(hours=1)][:12:2]
    col = (WIDTH - 355) / 6
    for i, p in enumerate(hourly):
        cx = 355 + col * i + col / 2
        local = p.time.astimezone(tz)
        c.text((cx, 98), local.strftime("%H"), 24, bold=True, anchor="mm")
        c.weather_icon((cx, 160), p.symbol, 46, dark(p.time))
        c.text((cx, 222), _deg(p.temp), 28, bold=True, anchor="mm")
        rain = sum(q.precip_mm for q in upcoming if p.time <= q.time < p.time + timedelta(hours=2))
        if rain >= 0.1:
            c.text((cx, 256), "%.1f" % rain, 20, role="rain", anchor="mm")
            c.text((cx, 280), "mm", 16, role="rain", anchor="mm")

    # Coming days
    c.hline(330)
    days = _days_from(forecast, today + timedelta(days=1), 7)
    col = WIDTH / 7
    for i, d in enumerate(days):
        cx = col * i + col / 2
        if i:
            c.vline(int(col * i), 345, 465)
        weekend = d.date.weekday() >= 5
        c.text((cx, 352), _day_name(d.date, lang, today), 26, role="weekend" if weekend else "fg",
               bold=True, anchor="mm")
        c.weather_icon((cx, 400), d.symbol, 48, False)
        c.text((cx - 4, 446), _deg(d.tmax), 24, role="tmax", bold=True, anchor="rm")
        c.text((cx + 4, 446), _deg(d.tmin), 24, role="tmin", bold=True, anchor="lm")
        if _mm(d.precip_mm):
            c.text((cx, 470), _mm(d.precip_mm), 16, role="rain", anchor="mm")


def layout_week(c, forecast, location, now, tz, lang, night):
    today = now.date()
    days = _days_from(forecast, today, 8)
    tw, th = WIDTH / 4, (HEIGHT - 120) / 2
    for i, d in enumerate(days):
        x0 = (i % 4) * tw
        y0 = 74 + (i // 4) * th
        cx = x0 + tw / 2
        if i % 4:
            c.vline(int(x0), int(y0 + 8), int(y0 + th - 8))
        weekend = d.date.weekday() >= 5
        c.text((cx, y0 + 20), _day_name(d.date, lang, today), 28,
               role="weekend" if weekend else "fg", bold=True, anchor="mm")
        today_dark = not is_daylight(now, location["lat"], location["lon"])
        c.weather_icon((cx, y0 + 76), d.symbol, 60, today_dark if i == 0 else False)
        c.text((cx - 5, y0 + 134), _deg(d.tmax), 30, role="tmax", bold=True, anchor="rm")
        c.text((cx + 5, y0 + 134), _deg(d.tmin), 30, role="tmin", bold=True, anchor="lm")
        if _mm(d.precip_mm):
            c.text((cx, y0 + 162), _mm(d.precip_mm), 18, role="rain", anchor="mm")
    c.hline(434, width=1)
    _sun_row(c, (16, 457), location, now, tz, lang)
    cur = _current_point(forecast, now)
    c.text((WIDTH - 16, 457), "%s %s" % (strings(lang)["now"], _deg(cur.temp)), 28,
           bold=True, anchor="rm")


LAYOUTS = {"overview": layout_overview, "week": layout_week}


def render(forecast, location, now, tz, lang="sv", layout="overview", night=False, error=None):
    """Return a PIL image. `forecast` may be None when nothing has ever been fetched."""
    c = Canvas("night" if night else "day")
    _header(c, location, now, lang, forecast, error)
    if forecast and forecast.points:
        LAYOUTS.get(layout, layout_overview)(c, forecast, location, now, tz, lang, night)
    else:
        c.icon((WIDTH // 2, 250), "cloud-refresh", 140, "fg")
        c.text((WIDTH // 2, 380), strings(lang)["error"], 30, anchor="mm")
    return c.img


def render_info(info, cfg, now, version):
    """Addresses and status, for helping someone over the phone."""
    s = strings(cfg["language"])
    c = Canvas("day")
    c.text((16, 34), s["info"], 40, bold=True, anchor="lm")
    c.text((WIDTH - 16, 34), now.strftime("%H:%M"), 34, bold=True, anchor="rm")
    c.hline(70)
    ts = info.get("tailscale")
    rows = [
        (s["network"], info.get("ssid") or s["no_wifi"]),
        ("IP", ", ".join(info.get("ips") or []) or "–"),
        (s["remote"], ("%s  %s" % (ts.get("name") or "", ts.get("ip") or "")).strip()
         if ts else s["not_connected"]),
        (s["dashboard"], "http://%s.local:8080" % info.get("hostname", "")),
        ("Host", info.get("hostname", "")),
        ("Version", version),
    ]
    y = 110
    for label, value in rows:
        c.text((24, y), label, 26, anchor="lm")
        c.text((230, y), value, 28, bold=True, anchor="lm")
        y += 52
    c.hline(424, width=1)
    c.text((WIDTH // 2, 452), s["buttons_help"], 22, anchor="mm")
    return c.img


def render_setup(hotspot, cfg):
    """Shown while the setup hotspot is up: three steps to get back online."""
    s = strings(cfg["language"])
    c = Canvas("day")
    c.icon((70, 52), "cloud-refresh", 60, "rain")
    c.text((130, 52), s["setup_title"], 34, bold=True, anchor="lm")
    c.hline(100)
    values = [hotspot.get("ssid", ""), hotspot.get("password", ""), hotspot.get("url", "")]
    y = 160
    for step, value in zip(s["setup_steps"], values):
        c.text((40, y), step, 28, anchor="lm")
        c.text((80, y + 50), value, 44, role="red", bold=True, anchor="lm")
        y += 110
    return c.img
