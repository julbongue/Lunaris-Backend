from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CombinedPoint:
    """Sun and Earth topocentric coordinates at one sampled instant."""

    timestamp: datetime
    sun_azimuth_deg: float
    sun_elevation_deg: float
    earth_azimuth_deg: float
    earth_elevation_deg: float


@dataclass(frozen=True)
class EphemerisBundle:
    points: list[CombinedPoint]
    warnings: list[str] = field(default_factory=list)
