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


class InkyDisplay:
    def __init__(self):
        from inky.auto import auto  # imported lazily: only present on the Pi
        self.inky = auto(ask_user=False, verbose=True)
        log.info("detected %s %dx%d", type(self.inky).__name__, *self.inky.resolution)

    def show(self, img, rotate=0, saturation=0.5):
        frame = img.rotate(rotate, expand=True)
        if frame.size != tuple(self.inky.resolution):
            frame = frame.resize(self.inky.resolution)
        try:
            self.inky.set_image(frame, saturation=saturation)
        except TypeError:  # drivers without a saturation argument
            self.inky.set_image(frame)
        self.inky.show()


def open_display(preview_path=None):
    if preview_path:
        return PngDisplay(preview_path)
    try:
        return InkyDisplay()
    except Exception as exc:  # no panel, no library, or not a Pi
        # systemd's RuntimeDirectory is writable; the install folder belongs to root
        path = os.path.join(os.environ.get("RUNTIME_DIRECTORY", "."), "preview.png")
        log.warning("no Inky display (%s); writing %s instead", exc, path)
        return PngDisplay(path)
