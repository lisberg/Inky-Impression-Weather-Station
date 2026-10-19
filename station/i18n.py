STRINGS = {
    "sv": {
        "days": ["mån", "tis", "ons", "tor", "fre", "lör", "sön"],
        "months": ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
        "today": "Idag",
        "now": "Nu",
        "updated": "Uppdaterad",
        "offline": "Ingen anslutning, visar senaste prognos",
        "error": "Kunde inte hämta väder",
        "midnight_sun": "Midnattssol",
        "polar_night": "Polarnatt",
        "feels": "Vind",
    },
    "en": {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "today": "Today",
        "now": "Now",
        "updated": "Updated",
        "offline": "Offline, showing last forecast",
        "error": "Could not fetch weather",
        "midnight_sun": "Midnight sun",
        "polar_night": "Polar night",
        "feels": "Wind",
    },
}


def t(lang):
    return STRINGS.get(lang, STRINGS["en"])
