"""Thin wrapper around Pimoroni's inky library, with a PNG fallback."""
import logging
import os

log = logging.getLogger(__name__)


class PngDisplay:
    """Writes the frame to a file; used off the Pi and for previews."""

    def __init__(self, path):
        self.path = path

    def show(self, img, rotate=0, saturation=0.5):
        img.rotate(rotate, expand=True).save(self.path)
        log.info("wrote %s", self.path)


def _inky(model):
    # imported lazily: only present on the Pi
    if model == "spectra73":
        from inky.inky_e673 import Inky
        return Inky(resolution=(800, 480))
    if model == "impressions73":
        from inky.inky_ac073tc1a import Inky
        return Inky(resolution=(800, 480))
    from inky.auto import auto
    try:
        return auto(ask_user=False, verbose=True)
    except RuntimeError as exc:
        # some boards come with a blank or unreadable ID chip; this project is
        # built for the 2025 Impression 7.3" (Spectra 6), so try that
        log.warning("%s; assuming an Inky Impression 7.3\" Spectra 6", exc)
        return _inky("spectra73")


class InkyDisplay:
    def __init__(self, model="auto"):
        self.inky = _inky(model)
        log.info("using %s %dx%d", type(self.inky).__name__, *self.inky.resolution)

    def show(self, img, rotate=0, saturation=0.5):
        frame = img.rotate(rotate, expand=True)
        if frame.size != tuple(self.inky.resolution):
            frame = frame.resize(self.inky.resolution)
        try:
            self.inky.set_image(frame, saturation=saturation)
        except TypeError:  # drivers without a saturation argument
            self.inky.set_image(frame)
        self.inky.show()


def open_display(preview_path=None, model="auto"):
    if preview_path:
        return PngDisplay(preview_path)
    try:
        return InkyDisplay(model)
    except Exception as exc:  # no panel, no library, or not a Pi
        # systemd's RuntimeDirectory is writable; the install folder belongs to root
        path = os.path.join(os.environ.get("RUNTIME_DIRECTORY", "."), "preview.png")
        log.warning("no Inky display (%s); writing %s instead", exc, path)
        return PngDisplay(path)
