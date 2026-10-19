from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class Point:
    """One step of a provider's time series. Times are timezone-aware UTC."""
    time: datetime
    temp: Optional[float]
    symbol: Optional[str]          # Yr-style symbol code, e.g. "partlycloudy_day"
    wind_speed: Optional[float] = None
    wind_dir: Optional[float] = None
    precip_mm: float = 0.0         # precipitation that falls in [precip_from, precip_to)
    precip_from: Optional[datetime] = None
    precip_to: Optional[datetime] = None
    symbol_6h: Optional[str] = None  # symbol for the following 6 h, when the provider has one


@dataclass
class Day:
    date: date
    tmin: Optional[float]
    tmax: Optional[float]
    precip_mm: float
    symbol: Optional[str]
    wind_max: Optional[float] = None


@dataclass
class Forecast:
    location: str
    provider: str
    fetched: datetime
    points: List[Point]
    days: List[Day] = field(default_factory=list)
    stale: bool = False            # True when served from cache after a failed fetch
