from . import smhi, yr
from .base import ProviderError

PROVIDERS = {yr.NAME: yr, smhi.NAME: smhi}


def get_forecast(location, tz, contact=""):
    provider = PROVIDERS.get(location.get("provider", "yr"))
    if provider is None:
        raise ProviderError("unknown provider %r" % location.get("provider"))
    return provider.get_forecast(location, tz, contact)


__all__ = ["PROVIDERS", "ProviderError", "get_forecast"]
