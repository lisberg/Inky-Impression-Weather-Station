"""Map Yr symbol codes to Weather Icons glyphs and an accent colour."""

# Order matters: the first matching keyword wins.
_RULES = (
    # keyword in symbol, day icon, night icon, colour role
    ("snowshowersandthunder", "day-snow-thunderstorm", "night-alt-snow-thunderstorm", "thunder"),
    ("sleetshowersandthunder", "day-sleet-storm", "night-alt-sleet-storm", "thunder"),
    ("snowandthunder", "snow-thunderstorm", "snow-thunderstorm", "thunder"),
    ("sleetandthunder", "sleet-storm", "sleet-storm", "thunder"),
    ("rainshowersandthunder", "day-storm-showers", "night-alt-storm-showers", "thunder"),
    ("thunder", "thunderstorm", "thunderstorm", "thunder"),
    ("snowshowers", "day-snow", "night-alt-snow", "snow"),
    ("snow", "snow", "snow", "snow"),
    ("sleetshowers", "day-sleet", "night-alt-sleet", "snow"),
    ("sleet", "sleet", "sleet", "snow"),
    ("lightrainshowers", "day-sprinkle", "night-alt-sprinkle", "rain"),
    ("rainshowers", "day-showers", "night-alt-showers", "rain"),
    ("lightrain", "sprinkle", "sprinkle", "rain"),
    ("rain", "rain", "rain", "rain"),
    ("fog", "fog", "night-fog", "cloud"),
    ("partlycloudy", "day-cloudy", "night-alt-cloudy", "sun"),
    ("fair", "day-sunny-overcast", "night-alt-partly-cloudy", "sun"),
    ("clearsky", "day-sunny", "night-clear", "sun"),
    ("cloudy", "cloudy", "cloudy", "cloud"),
)


def icon_for(symbol, night=None):
    """Return (icon name, colour role). `night` overrides the _day/_night suffix."""
    if not symbol:
        return "na", "cloud"
    if night is None:
        night = symbol.endswith("_night") or symbol.endswith("_polartwilight")
    base = symbol.split("_")[0]
    for key, day_icon, night_icon, role in _RULES:
        if key in base:
            return (night_icon if night else day_icon), role
    return "na", "cloud"
