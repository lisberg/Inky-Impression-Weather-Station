# Inky Impression Weather Station

A configurable weather station for the Pimoroni Inky Impression 7.3" e-ink
display (800×480), driven by a Raspberry Pi Zero 2 W.

| Day | Night |
|---|---|
| ![Overview, day](docs/preview-overview-day.png) | ![Overview, night](docs/preview-overview-night.png) |
| ![Week, day](docs/preview-week-day.png) | ![Week, night](docs/preview-week-night.png) |

- Forecasts from **Yr / MET Norway** or **SMHI**, chosen per location. No API key needed.
- Any number of saved locations.
- Two layouts: `overview` (now, next 12 hours, 7 days) and `week` (8 day tiles).
- Clock, date, sunrise and sunset, with midnight sun and polar night handled.
- Night theme (light text on black) after sunset, or forced on/off.
- Keeps showing the last forecast when the network drops, with a notice.

The screen redraws every 15 minutes by default. A full refresh of the 7.3"
panel takes about 30 seconds and flashes, so a ticking clock isn't practical;
the clock shows the time of the last redraw.

## Install

Set up the panel with Pimoroni's [inky library](https://github.com/pimoroni/inky)
first, then:

```
git clone https://github.com/lisberg/Inky-Impression-Weather-Station.git
cd Inky-Impression-Weather-Station
pip3 install -r requirements.txt
cp config.example.json config.json
nano config.json
python3 -m station --once
```

To run it on boot:

```
sudo cp Inky-Impression-Weather-Station.service /etc/systemd/system/
sudo systemctl enable --now Inky-Impression-Weather-Station
```

## Configuration

`config.json` (any key you leave out takes its default):

| Key | Meaning |
|---|---|
| `locations` | List of `{"name", "lat", "lon", "provider"}`; provider is `yr` or `smhi` (SMHI covers the Nordic area only). A location can also set its own `timezone`. |
| `active_location` | Index into `locations` of the one shown. |
| `timezone` | IANA zone, e.g. `Europe/Stockholm`. |
| `language` | `sv` or `en`. |
| `layout` | `overview` or `week`. |
| `refresh_minutes` | Minutes between redraws, at least 5. |
| `night_mode` | `auto` (dark between sunset and sunrise), `on` or `off`. |
| `quiet_hours` | `{"start": "23:00", "end": "06:00"}` pauses redraws overnight; empty strings disable it. |
| `display` | `rotate` (0/90/180/270) and `saturation` (0–1). |
| `contact` | Your e-mail or URL. MET Norway asks every client to identify itself. |

## Development

Everything except the panel driver runs on any machine:

```
pip3 install pillow requests pytest
python3 -m pytest
python3 tools/preview.py                     # renders docs/preview-*.png from sample data
python3 -m station --preview out.png         # live data, written to a PNG
```

## Credit

- Original code by [Rainer Bunger](https://github.com/rbunger/Inky-wHAT-Weather-Station).
- Weather icons by [Erik Flowers](https://github.com/erikflowers/weather-icons), SIL OFL 1.1.
- Atkinson Hyperlegible font by the Braille Institute, SIL OFL 1.1.
- Weather data from [MET Norway](https://api.met.no) (CC BY 4.0) and [SMHI](https://opendata.smhi.se) (CC BY 4.0).
