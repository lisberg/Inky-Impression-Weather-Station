import pytest

from station import app as appmod
from station import config, web
from station.providers import base, yr
from tests import samples
from tests.test_station import NullDisplay


class FakeNM:
    """Just enough nmcli for the dashboard: two saved networks, three visible."""

    def __init__(self):
        self.cons = {"Hemma": ("Hemma", 5, True), "Mobil": ("Mobil", 0, False)}
        self.calls = []

    def __call__(self, *args, timeout=30):
        self.calls.append(args)
        if args[:5] == ("-t", "-f", "NAME,TYPE,ACTIVE", "connection", "show"):
            rows = ["%s:802-11-wireless:%s" % (n, "yes" if a else "no") for n, (_, _, a) in self.cons.items()]
            return "\n".join(rows + ["lo:loopback:yes"]) + "\n"
        if args[:2] == ("-t", "-g"):
            ssid, prio, _ = self.cons[args[-1]]
            return "%s\n%d\n" % (ssid, prio)
        if "wifi" in args and "list" in args:
            return "Hemma:80:WPA2\nGranne\\:5G:60:WPA2\nCafe:40:--\n"
        if args[:2] == ("connection", "add"):
            name = args[args.index("con-name") + 1]
            prio = int(args[args.index("connection.autoconnect-priority") + 1])
            self.cons[name] = (name, prio, False)
        if args[:2] == ("connection", "delete"):
            self.cons.pop(args[2], None)
        return ""


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = str(tmp_path / "c.json")
    config.save(config.load(path), path)
    st = appmod.Station(path, NullDisplay())
    tz_fc = lambda loc, tz, contact="": base.make_forecast(  # noqa: E731
        loc, "yr", yr.parse(samples.yr_payload()), False, tz)
    monkeypatch.setattr(appmod, "get_forecast", tz_fc)
    nm = FakeNM()
    geo = lambda q, lang: [{"name": "Sundsvall", "label": "Sundsvall, Sverige",  # noqa: E731
                            "lat": 62.3908, "lon": 17.3069}]
    client = web.create_app(st, wifi_run=nm, geocoder=geo).test_client()
    return st, nm, client


H = {"Origin": "http://localhost"}


def test_index_and_preview(env):
    st, nm, client = env
    page = client.get("/?q=sundsvall").get_data(as_text=True)
    assert "Stockholm" in page and "Sundsvall, Sverige" in page
    assert "Granne:5G" in page and "Hemma" in page
    png = client.get("/preview.png")
    assert png.status_code == 200 and png.data[:4] == b"\x89PNG"


def test_dashboard_assets_and_events(env):
    st, nm, client = env
    assert client.get("/static/dashboard.css").status_code == 200
    assert client.get("/static/htmx-2.0.4.min.js").status_code == 200
    web.capture_events()
    import logging
    logging.getLogger("station").warning("hello from the test")
    page = client.get("/").get_data(as_text=True)
    assert "data-theme-toggle" in page and "hello from the test" in page


def test_cross_site_post_is_rejected(env):
    st, nm, client = env
    assert client.post("/refresh", headers={"Origin": "http://evil.example"}).status_code == 403
    assert client.post("/refresh").status_code == 403


def test_add_show_reorder_delete_location(env):
    st, nm, client = env
    client.post("/locations/add", data={"name": "Sundsvall", "lat": "62.39", "lon": "17.31",
                                        "provider": "smhi"}, headers=H)
    client.post("/locations/1/show", headers=H)
    assert config.active_location(st.load_config())["name"] == "Sundsvall"
    client.post("/locations/1/up", headers=H)
    cfg = st.load_config()
    assert [l["name"] for l in cfg["locations"]] == ["Sundsvall", "Stockholm"]
    assert cfg["active_location"] == 0  # still showing Sundsvall
    client.post("/locations/1/delete", headers=H)
    assert [l["name"] for l in st.load_config()["locations"]] == ["Sundsvall"]
    client.post("/locations/0/delete", headers=H)  # the last one stays
    assert len(st.load_config()["locations"]) == 1
    assert st.wake.is_set()


def test_change_location_provider(env):
    st, nm, client = env
    client.post("/locations/0/provider", data={"provider": "smhi"}, headers=H)
    assert st.load_config()["locations"][0]["provider"] == "smhi"
    r = client.post("/locations/0/provider", data={"provider": "bogus"}, headers=H,
                    follow_redirects=True)
    assert "unknown provider" in r.get_data(as_text=True)
    assert st.load_config()["locations"][0]["provider"] == "smhi"
    assert 'value="smhi" selected' in client.get("/").get_data(as_text=True)


def test_bad_location_is_reported(env):
    st, nm, client = env
    r = client.post("/locations/add", data={"name": "X", "lat": "abc", "lon": "1"}, headers=H,
                    follow_redirects=True)
    assert "numeric" in r.get_data(as_text=True)
    assert len(st.load_config()["locations"]) == 1


def test_settings(env):
    st, nm, client = env
    client.post("/settings", data={"layout": "week", "night_mode": "off", "language": "en",
                                   "refresh_minutes": "30", "quiet_start": "23:00",
                                   "quiet_end": "06:00", "rotate": "180", "contact": "a@b.se"},
                headers=H)
    cfg = st.load_config()
    assert (cfg["layout"], cfg["night_mode"], cfg["language"], cfg["refresh_minutes"]) == \
        ("week", "off", "en", 30)
    assert cfg["display"]["rotate"] == 180 and cfg["quiet_hours"]["start"] == "23:00"


def test_wifi_add_and_delete(env):
    st, nm, client = env
    client.post("/wifi/add", data={"ssid": "Cafe", "password": "", "priority": "2"}, headers=H)
    assert "Cafe" in nm.cons
    r = client.post("/wifi/add", data={"ssid": "Kort", "password": "short"}, headers=H,
                    follow_redirects=True)
    assert "8 to 63" in r.get_data(as_text=True) and "Kort" not in nm.cons
    client.post("/wifi/delete", data={"name": "Mobil"}, headers=H)
    assert "Mobil" not in nm.cons


def test_password(env):
    st, nm, client = env
    st.update_config(lambda c: c["dashboard"].update(password="hemligt"))
    assert client.get("/").status_code == 401
    import base64
    ok = {"Authorization": "Basic " + base64.b64encode(b"x:hemligt").decode()}
    assert client.get("/", headers=ok).status_code == 200
