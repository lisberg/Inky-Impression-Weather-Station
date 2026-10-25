"""The four buttons on the side of the Inky Impression.

A: next location   B: previous location   C: next layout
D: refresh now     hold D: info screen (addresses for remote help)
"""
import logging

log = logging.getLogger(__name__)
HOLD_SECONDS = 3


def attach(station, pins):
    try:
        from gpiozero import Button  # Raspberry Pi OS ships it; absent elsewhere
    except ImportError:
        log.warning("gpiozero not available, buttons disabled")
        return []
    try:
        a, b, c, d = [Button(pin, pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS)
                      for pin in pins]
    except Exception:
        # a broken GPIO setup must not keep the forecast off the screen
        log.exception("could not claim button pins %s, buttons disabled", pins)
        return []
    a.when_pressed = lambda: station.press("next_location")
    b.when_pressed = lambda: station.press("previous_location")
    c.when_pressed = lambda: station.press("next_layout")
    # D: a short press refreshes on release; holding it opens the info screen instead
    held = {"d": False}

    def d_held():
        held["d"] = True
        station.press("info")

    def d_released():
        if not held["d"]:
            station.press("refresh")
        held["d"] = False

    d.when_held = d_held
    d.when_released = d_released
    log.info("buttons on BCM %s", pins)
    return [a, b, c, d]  # keep references, or gpiozero releases the pins
