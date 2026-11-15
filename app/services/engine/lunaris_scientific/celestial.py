"""Celestial body position inputs and apparent-direction calculations.

This module does **not** compute ephemerides. It consumes body positions
provided by external ephemeris sources (e.g. SPICE/JPL Horizons integration in
backend) and computes observer-relative vectors and horizontal coordinates.

All external positions must be explicitly tagged with their reference frame and
units by the caller. Synthetic test fixtures must be labeled as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .frames import LocalFrame, direction_to_horizontal, local_frame
from .vectors import Vec3, distance, norm, vec3


@dataclass(frozen=True, slots=True)
class BodyState:
    """Position of a celestial body at an instant.

    position_body_km: Cartesian position vector in a declared frame, kilometers.
    frame: textual frame identifier (e.g. "MOON_ME", "ICRF", "SELENOGRAPHIC").
    time_utc: observation instant in UTC.
    source: provenance label, e.g. "jpl_horizons", "synthetic_fixture".
    """

    position_body_km: Vec3
    frame: str
    time_utc: datetime
    source: str


@dataclass(frozen=True, slots=True)
class ApparentPosition:
    azimuth_deg: float
    altitude_deg: float
    distance_km: Optional[float]
    direction_body: Vec3  # unitless direction in same frame as inputs after delta


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def apparent_position_from_observer(
    observer_body_km: Vec3,
    target_body_km: Vec3,
    observer_frame: LocalFrame,
) -> ApparentPosition:
    """Compute apparent azimuth/altitude of target seen from observer.

    Assumes observer and target vectors are expressed in the same body-fixed
    Cartesian frame as ``observer_frame``. Frame transformations (e.g. inertial
    to body-fixed using lunar orientation at time) must be performed by the
    caller/integration layer when ephemeris provides inertial vectors.
    """
    delta = target_body_km - observer_body_km
    dist = norm(delta)
    az, alt = direction_to_horizontal(observer_frame, delta)
    # direction as unit vector in body frame
    if dist == 0:
        raise ValueError("Observer and target positions coincide")
    direction = vec3(delta.x / dist, delta.y / dist, delta.z / dist)
    return ApparentPosition(
        azimuth_deg=az,
        altitude_deg=alt,
        distance_km=dist,
        direction_body=direction,
    )
