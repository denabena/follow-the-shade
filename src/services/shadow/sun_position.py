from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from astral import Observer
from astral.sun import azimuth, elevation


@dataclass(frozen=True)
class SunPosition:
    azimuth_deg: float
    elevation_deg: float


def sun_at(lat: float, lng: float, when: datetime) -> SunPosition:
    observer = Observer(latitude=lat, longitude=lng)
    when_naive = when.replace(tzinfo=None) if when.tzinfo else when
    return SunPosition(
        azimuth_deg=float(azimuth(observer, when_naive)),
        elevation_deg=float(elevation(observer, when_naive)),
    )
