from datetime import datetime
from zoneinfo import ZoneInfo

from station import app, config, netwatch, render


class NullDisplay:
    def __init__(self):
        self.frames = []

    def show(self, img, rotate=0, saturation=0.5):
        self.frames.append(img)


def make_station(tmp_path):
    cfg = config.load(str(tmp_path / "c.json"))
    cfg["locations"] += [{"name": "Kiruna", "lat": 67.85, "lon": 20.22, "provider": "smhi"},
                         {"name": "Lund", "lat": 55.7, "lon": 13.19, "provider": "yr"}]
    config.save(cfg, str(tmp_path / "c.json"))
    return app.Station(str(tmp_path / "c.json"), NullDisplay())


def test_buttons_cycle_locations_and_layout(tmp_path):
    st = make_station(tmp_path)
    st.press("previous_location")
    cfg = st.apply_actions(st.load_config())
    assert cfg["active_location"] == 2
    for _ in range(2):
        st.press("next_location")
    st.press("next_layout")
    st.apply_actions(st.load_config())
    saved = st.load_config()
    assert saved["active_location"] == 1 and saved["layout"] == "week"
    assert st.wake.is_set()


def test_info_toggle(tmp_path):
    st = make_station(tmp_path)
    st.press("info")
    st.apply_actions(st.load_config())
    assert st.showing_info
    st.press("refresh")
    st.apply_actions(st.load_config())
    assert not st.showing_info


def test_quiet_hours():
    cfg = {"quiet_hours": {"start": "23:00", "end": "06:00"}}
    tz = ZoneInfo("Europe/Stockholm")
    assert app.in_quiet_hours(cfg, datetime(2026, 1, 1, 2, tzinfo=tz))
    assert not app.in_quiet_hours(cfg, datetime(2026, 1, 1, 12, tzinfo=tz))
    assert not app.in_quiet_hours({"quiet_hours": {"start": "", "end": ""}}, datetime.now(tz))


def test_info_and_setup_screens():
    cfg = config.load("/nonexistent.json")
    info = {"hostname": "vader", "ips": ["192.168.1.20"], "ssid": "Hemma",
            "tailscale": {"ip": "100.64.0.7", "name": "vader.tail1234.ts.net", "online": True}}
    img = render.render_info(info, cfg, datetime(2026, 10, 19, 12), "2.0.0")
    assert img.size == (800, 480)
    img = render.render_setup({"ssid": "Vaderstation-setup", "password": "vaderstation",
                               "url": "http://10.42.0.1"}, cfg)
    assert {c for _, c in img.getcolors(64)} <= set(render.INK.values())


class FakeNM:
    def __init__(self):
        self.state, self.con = "disconnected", ""
        self.calls = []

    def __call__(self, *args, check=True):
        self.calls.append(args)
        if args[:2] == ("connection", "up"):
            self.state, self.con = "connected", netwatch.CON_NAME
        if args[:2] == ("connection", "down"):
            self.state, self.con = "disconnected", ""
        if "device" in args:
            return "wlan0:%s:%s\nlo:connected (externally):lo\n" % (self.state, self.con)
        return ""


def test_netwatch_hotspot_cycle(tmp_path, monkeypatch):
    nm, now = FakeNM(), [0.0]
    w = netwatch.NetWatch(run=nm, clock=lambda: now[0], hotspot_file=str(tmp_path / "hs.json"),
                          scan_file=str(tmp_path / "scan.json"))
    monkeypatch.setattr(w, "hotspot_clients", lambda: 0)
    w.step("S", "password1")
    now[0] = netwatch.GRACE - 1
    w.step("S", "password1")
    assert w.hotspot_since is None              # still within the grace period
    now[0] = netwatch.GRACE + 1
    w.step("S", "password1")
    assert w.hotspot_since is not None and (tmp_path / "hs.json").exists()
    now[0] += netwatch.HOTSPOT_WINDOW + 1
    w.step("S", "password1")                    # nobody joined: give saved networks a go
    assert w.hotspot_since is None and not (tmp_path / "hs.json").exists()


def test_netwatch_leaves_hotspot_when_network_chosen(tmp_path):
    nm, now = FakeNM(), [0.0]
    w = netwatch.NetWatch(run=nm, clock=lambda: now[0], hotspot_file=str(tmp_path / "hs.json"),
                          scan_file=str(tmp_path / "scan.json"))
    w.start_hotspot("S", "password1")
    nm.state, nm.con = "connected", "Hemma"
    w.step("S", "password1")
    assert w.hotspot_since is None and not (tmp_path / "hs.json").exists()
    w.step("S", "password1")
    assert w.offline_since is None
