"""Settings, stored as one JSON file that the web dashboard can rewrite.

Missing keys fall back to DEFAULTS, so an old config keeps working when new
settings are added.
"""
import copy
import json
import os
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.environ.get("WEATHER_CONFIG", os.path.join(ROOT, "config.json"))
STATE_DIR = os.environ.get("WEATHER_STATE", os.path.join(ROOT, "state"))

PROVIDERS = ("yr", "smhi")
LAYOUTS = ("overview", "week")
NIGHT_MODES = ("auto", "on", "off")
LANGUAGES = ("sv", "en")

DEFAULTS = {
    "locations": [
        {"name": "Stockholm", "lat": 59.3293, "lon": 18.0686, "provider": "yr"},
    ],
    "active_location": 0,
    "timezone": "Europe/Stockholm",
    "language": "sv",
    "layout": "overview",
    "refresh_minutes": 15,
    # auto = dark theme between sunset and sunrise at the active location
    "night_mode": "auto",
    # no screen refresh in this window (local time, "HH:MM"); empty = never pause
    "quiet_hours": {"start": "", "end": ""},
    "display": {"rotate": 0, "saturation": 0.5},
    # MET Norway requires a contact in the User-Agent of every request
    "contact": "",
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class ConfigError(ValueError):
    pass


def validate(cfg):
    locs = cfg.get("locations")
    if not isinstance(locs, list) or not locs:
        raise ConfigError("at least one location is required")
    for i, loc in enumerate(locs):
        if not str(loc.get("name", "")).strip():
            raise ConfigError("location %d has no name" % (i + 1))
        try:
            lat, lon = float(loc["lat"]), float(loc["lon"])
        except (KeyError, TypeError, ValueError):
            raise ConfigError("location '%s' needs numeric lat/lon" % loc.get("name"))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ConfigError("location '%s' has lat/lon out of range" % loc["name"])
        loc["lat"], loc["lon"] = lat, lon
        loc.setdefault("provider", "yr")
        if loc["provider"] not in PROVIDERS:
            raise ConfigError("unknown provider '%s'" % loc["provider"])
    if not isinstance(cfg.get("active_location"), int) or not 0 <= cfg["active_location"] < len(locs):
        cfg["active_location"] = 0
    for key, allowed in (("layout", LAYOUTS), ("night_mode", NIGHT_MODES), ("language", LANGUAGES)):
        if cfg.get(key) not in allowed:
            raise ConfigError("%s must be one of %s" % (key, ", ".join(allowed)))
    if not isinstance(cfg.get("refresh_minutes"), (int, float)) or cfg["refresh_minutes"] < 5:
        raise ConfigError("refresh_minutes must be at least 5")
    if cfg["display"].get("rotate") not in (0, 90, 180, 270):
        raise ConfigError("display.rotate must be 0, 90, 180 or 270")
    return cfg


def load(path=DEFAULT_PATH):
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    return validate(_merge(DEFAULTS, data))


def save(cfg, path=DEFAULT_PATH):
    """Validate and write atomically, so a power cut never leaves half a file."""
    cfg = validate(_merge(DEFAULTS, cfg))
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".config-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return cfg


def active_location(cfg):
    return cfg["locations"][cfg["active_location"]]
