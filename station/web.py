"""Settings dashboard, served by the station process on port 8080.

Running inside the station process means the dashboard can wake the display
directly and reuse its forecast cache for the preview.
"""
import hmac
import io
import logging
import secrets
import threading
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import requests
from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

from . import __version__, netinfo, wifi
from . import config as cfgmod
from .providers.base import USER_AGENT

log = logging.getLogger("web")

GEOCODER = "https://nominatim.openstreetmap.org/search"

EVENTS = deque(maxlen=40)  # newest first, shown on the System tab


class EventLog(logging.Handler):
    """Keeps the station's recent log lines for the dashboard (not the HTTP access log)."""

    def emit(self, record):
        if record.name == "werkzeug":
            return
        EVENTS.appendleft({"time": time.strftime("%H:%M:%S", time.localtime(record.created)),
                           "level": record.levelname.lower(), "source": record.name.split(".")[-1],
                           "message": record.getMessage().splitlines()[0]})


def capture_events():
    root = logging.getLogger()
    if not any(isinstance(h, EventLog) for h in root.handlers):
        root.addHandler(EventLog(logging.INFO))

TEXT = {
    "sv": {
        "title": "Väderstation", "screen": "Skärmen", "refresh": "Uppdatera skärmen nu",
        "refresh_note": "Skärmen ritas om på ungefär 30 sekunder.",
        "locations": "Platser", "show": "Visa", "showing": "Visas", "up": "Upp", "down": "Ner",
        "delete": "Ta bort", "search": "Sök plats", "search_hint": "t.ex. Sundsvall",
        "add": "Lägg till", "name": "Namn", "lat": "Latitud", "lon": "Longitud",
        "provider": "Källa", "manual": "Lägg till med koordinater", "no_results": "Hittade inget.",
        "display": "Visning", "layout": "Vy", "overview": "Översikt", "week": "Vecka",
        "night_mode": "Nattläge", "auto": "Automatiskt vid solnedgång", "on": "Alltid", "off": "Aldrig",
        "language": "Språk", "refresh_minutes": "Uppdatera var (minuter)",
        "quiet": "Ingen uppdatering mellan", "and": "och", "rotate": "Rotera skärmen",
        "contact": "Kontakt (e-post, krävs av MET Norway)", "save": "Spara",
        "wifi": "WiFi", "saved_networks": "Sparade nätverk", "connected": "Ansluten",
        "priority": "Prioritet", "visible": "Nätverk i närheten", "password": "Lösenord",
        "connect_now": "Anslut direkt", "add_network": "Lägg till nätverk",
        "switching": "Byter till %s. Om det misslyckas kommer installationsnätverket tillbaka om två minuter.",
        "system": "System", "hostname": "Värdnamn", "remote": "Fjärrhjälp (Tailscale)",
        "not_connected": "inte ansluten", "version": "Version", "saved": "Sparat.",
        "setup_banner": "Stationen saknar WiFi. Välj ett nätverk nedan.",
        "confirm_delete": "Ta bort?",
        "now_showing": "Visas nu", "updated": "Uppdaterad %s", "not_drawn": "Inte uppritad än",
        "day": "Dagläge", "night": "Nattläge", "switch": "Byt plats",
        "theme": "Tema", "theme_auto": "Följ systemet", "theme_light": "Ljust", "theme_dark": "Mörkt",
        "last_update": "Senaste uppdatering", "signal": "WiFi-signal", "events": "Händelser",
        "no_events": "Inga händelser än.", "online": "Ansluten", "sections": "Avsnitt",
        "move": "Flytta",
    },
    "en": {
        "title": "Weather station", "screen": "Screen", "refresh": "Refresh the screen now",
        "refresh_note": "The screen redraws in about 30 seconds.",
        "locations": "Locations", "show": "Show", "showing": "Showing", "up": "Up", "down": "Down",
        "delete": "Delete", "search": "Find a place", "search_hint": "e.g. Sundsvall",
        "add": "Add", "name": "Name", "lat": "Latitude", "lon": "Longitude",
        "provider": "Source", "manual": "Add by coordinates", "no_results": "Nothing found.",
        "display": "Display", "layout": "Layout", "overview": "Overview", "week": "Week",
        "night_mode": "Night mode", "auto": "Automatic at sunset", "on": "Always", "off": "Never",
        "language": "Language", "refresh_minutes": "Refresh every (minutes)",
        "quiet": "No refresh between", "and": "and", "rotate": "Rotate screen",
        "contact": "Contact (e-mail, required by MET Norway)", "save": "Save",
        "wifi": "WiFi", "saved_networks": "Saved networks", "connected": "Connected",
        "priority": "Priority", "visible": "Networks nearby", "password": "Password",
        "connect_now": "Connect now", "add_network": "Add network",
        "switching": "Switching to %s. If that fails, the setup network comes back in two minutes.",
        "system": "System", "hostname": "Hostname", "remote": "Remote help (Tailscale)",
        "not_connected": "not connected", "version": "Version", "saved": "Saved.",
        "setup_banner": "The station has no WiFi. Pick a network below.",
        "confirm_delete": "Delete?",
        "now_showing": "Showing now", "updated": "Updated %s", "not_drawn": "Not drawn yet",
        "day": "Day mode", "night": "Night mode", "switch": "Switch place",
        "theme": "Theme", "theme_auto": "Match system", "theme_light": "Light", "theme_dark": "Dark",
        "last_update": "Last update", "signal": "WiFi signal", "events": "Events",
        "no_events": "No events yet.", "online": "Connected", "sections": "Sections",
        "move": "Move",
    },
}


def geocode(query, lang):
    resp = requests.get(GEOCODER, params={"q": query, "format": "jsonv2", "limit": 6,
                                          "accept-language": lang},
                        headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    out = []
    for r in resp.json():
        label = r.get("display_name", "")
        out.append({"name": r.get("name") or label.split(",")[0], "label": label,
                    "lat": round(float(r["lat"]), 4), "lon": round(float(r["lon"]), 4)})
    return out


def create_app(station, wifi_run=wifi.nmcli, geocoder=geocode):
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(16)

    def cfg():
        return station.load_config()

    def changed(message=None):
        station.press("refresh")
        flash(message or TEXT[cfg()["language"]]["saved"])
        return redirect(url_for("index") + (request.form.get("anchor") or ""))

    @app.before_request
    def guard():
        password = cfg()["dashboard"].get("password")
        if password:
            auth = request.authorization
            if not auth or not hmac.compare_digest(auth.password or "", password):
                return Response("Login required", 401,
                                {"WWW-Authenticate": 'Basic realm="weather station"'})
        if request.method == "POST":
            # Block cross-site form posts: another page in the browser must not be
            # able to change settings on the LAN.
            source = request.headers.get("Origin") or request.headers.get("Referer")
            if not source or urlparse(source).netloc != request.host:
                abort(403)

    @app.get("/")
    def index():
        c = cfg()
        t = TEXT[c["language"]]
        query = request.args.get("q", "").strip()
        results, search_error = [], None
        if query:
            try:
                results = geocoder(query, c["language"])
            except Exception as exc:  # network down, rate limited
                search_error = str(exc)
        try:
            saved = wifi.saved(wifi_run)
            visible = wifi.scan(wifi_run, rescan=False)
        except wifi.WifiError as exc:
            saved, visible = [], []
            log.warning("wifi listing failed: %s", exc)
        saved_ssids = {n["ssid"] for n in saved}
        info = netinfo.summary()
        signal = next((v["signal"] for v in visible if v["ssid"] == info["ssid"]), None)
        from .app import use_night_theme  # app imports this module when it starts
        loc = cfgmod.active_location(c)
        tz = ZoneInfo(loc.get("timezone") or c["timezone"])
        now = datetime.now(tz)
        last = station.last_refresh
        return render_template("dashboard.html", c=c, t=t, query=query, results=results,
                               search_error=search_error, saved=saved,
                               visible=[v for v in visible if v["ssid"] not in saved_ssids],
                               info=info, signal=signal, version=__version__,
                               night=use_night_theme(c, loc, now),
                               last_refresh=datetime.fromtimestamp(last, tz).strftime("%H:%M") if last else None,
                               events=list(EVENTS)[:15], stamp=int(last or 0),
                               providers=cfgmod.PROVIDERS, layouts=cfgmod.LAYOUTS)

    @app.get("/preview.png")
    def preview():
        c = cfg()
        img = station.frame(c, hotspot=netinfo.hotspot())
        buf = io.BytesIO()
        img.rotate(c["display"]["rotate"], expand=True).save(buf, "PNG")
        return Response(buf.getvalue(), mimetype="image/png",
                        headers={"Cache-Control": "no-store"})

    @app.post("/refresh")
    def refresh():
        station.press("refresh")
        flash(TEXT[cfg()["language"]]["refresh_note"])
        return redirect(url_for("index"))

    # --- locations ----------------------------------------------------------
    @app.post("/locations/add")
    def location_add():
        f = request.form
        loc = {"name": f.get("name", "").strip(), "lat": f.get("lat"), "lon": f.get("lon"),
               "provider": f.get("provider", "yr")}
        try:
            station.update_config(lambda c: c["locations"].append(loc))
        except cfgmod.ConfigError as exc:
            flash(str(exc), "error")
            return redirect(url_for("index") + "#locations")
        return changed()

    @app.post("/locations/<int:i>/<action>")
    def location_action(i, action):
        def change(c):
            locs = c["locations"]
            if not 0 <= i < len(locs):
                abort(404)
            active = locs[c["active_location"]]
            if action == "show":
                c["active_location"] = i
                return
            if action == "provider":
                locs[i]["provider"] = request.form.get("provider", "")
                return
            if action == "delete":
                if len(locs) == 1:
                    raise cfgmod.ConfigError("at least one location is required")
                locs.pop(i)
            elif action in ("up", "down"):
                j = i - 1 if action == "up" else i + 1
                if 0 <= j < len(locs):
                    locs[i], locs[j] = locs[j], locs[i]
            else:
                abort(404)
            # keep showing the same place after a reorder or delete
            c["active_location"] = locs.index(active) if active in locs else 0
        try:
            station.update_config(change)
        except cfgmod.ConfigError as exc:
            flash(str(exc), "error")
            return redirect(url_for("index") + "#locations")
        return changed()

    # --- display settings ---------------------------------------------------
    @app.post("/settings")
    def settings():
        f = request.form

        def change(c):
            c["layout"] = f.get("layout", c["layout"])
            c["night_mode"] = f.get("night_mode", c["night_mode"])
            c["language"] = f.get("language", c["language"])
            c["refresh_minutes"] = int(f.get("refresh_minutes") or c["refresh_minutes"])
            c["quiet_hours"] = {"start": f.get("quiet_start", ""), "end": f.get("quiet_end", "")}
            c["display"]["rotate"] = int(f.get("rotate") or 0)
            c["contact"] = f.get("contact", "").strip()
        try:
            station.update_config(change)
        except (cfgmod.ConfigError, ValueError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("index") + "#display")
        return changed()

    # --- WiFi ---------------------------------------------------------------
    @app.post("/wifi/add")
    def wifi_add():
        f = request.form
        ssid = f.get("ssid", "").strip()
        t = TEXT[cfg()["language"]]
        try:
            wifi.add(ssid, f.get("password", ""), int(f.get("priority") or 0), run=wifi_run)
        except (wifi.WifiError, ValueError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("index") + "#wifi")
        if f.get("connect"):
            wifi.connect_later(ssid, run=wifi_run)
            flash(t["switching"] % ssid)
        else:
            flash(t["saved"])
        return redirect(url_for("index") + "#wifi")

    @app.post("/wifi/priority")
    def wifi_priority():
        try:
            wifi.set_priority(request.form["name"], int(request.form.get("priority") or 0), run=wifi_run)
        except (wifi.WifiError, ValueError, KeyError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index") + "#wifi")

    @app.post("/wifi/delete")
    def wifi_delete():
        try:
            wifi.remove(request.form["name"], run=wifi_run)
        except (wifi.WifiError, KeyError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("index") + "#wifi")

    return app


def serve_in_background(station, port):
    capture_events()
    app = create_app(station)

    def run():
        from werkzeug.serving import make_server
        make_server("0.0.0.0", port, app, threaded=True).serve_forever()

    threading.Thread(target=run, name="dashboard", daemon=True).start()
    log.info("dashboard on http://%s.local:%d", netinfo.hostname(), port)
