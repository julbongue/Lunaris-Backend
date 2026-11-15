"""Topographic horizon and terrain obstruction calculations.

This module defines data structures and algorithms for horizon profiles derived
from a Digital Elevation Model (DEM). It does **not** load or invent DEM data.
Callers/integrators must supply real elevation profiles from external datasets
(e.g. LOLA) or explicitly synthetic fixtures for testing.

Expected DEM/profile interface (to be aligned with Hermes/backend integration):
- Profile samples along an azimuth ray from observer:
  - distance_m: surface/ground distance from observer along ray (meters)
  - elevation_m: terrain elevation relative to chosen lunar reference (meters)
  - or direct obstruction angles precomputed upstream
- Observer state: lat/lon/altitude_m or absolute radius/position
- Target directions: azimuth_deg, altitude_deg at observation times
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from .vectors import deg_to_rad, rad_to_deg


@dataclass(frozen=True, slots=True)
class TerrainProfileSample:
    """One sample in a topographic profile along a line of sight/azimuth."""

    distance_m: float
    terrain_elevation_m: float


@dataclass(frozen=True, slots=True)
class HorizonObstructionResult:
    blocked: bool
    target_altitude_deg: float
    max_obstruction_angle_deg: float | None
    horizon_reference: str = "topographic"
    azimuth_deg: float | None = None
    profile_source: str = "unknown"


def obstruction_angle_deg(
    observer_elevation_m: float,
    sample: TerrainProfileSample,
    *,
    observer_height_m: float = 0.0,
) -> float:
    """Approximate elevation angle of a terrain sample seen by observer.

    Uses a planar approximation: angle = atan2(h_terrain - h_obs, distance).
    For long lunar baselines, integrators may supply geodetically corrected
    profiles/angles; this function documents the baseline mathematical method.
    """
    if sample.distance_m <= 0:
        raise ValueError("distance_m must be > 0")
    dh = sample.terrain_elevation_m - (observer_elevation_m + observer_height_m)
    return rad_to_deg(math.atan2(dh, sample.distance_m))


def max_obstruction_angle(
    observer_elevation_m: float,
    profile: Sequence[TerrainProfileSample],
    *,
    observer_height_m: float = 0.0,
) -> float | None:
    if not profile:
        return None
    return max(
        obstruction_angle_deg(observer_elevation_m, s, observer_height_m=observer_height_m)
        for s in profile
    )


def is_blocked_by_terrain(
    target_altitude_deg: float,
    observer_elevation_m: float,
    profile: Sequence[TerrainProfileSample],
    *,
    observer_height_m: float = 0.0,
    azimuth_deg: float | None = None,
    profile_source: str = "unknown",
    margin_deg: float = 0.0,
) -> HorizonObstructionResult:
    """Determine if target is below the topographic horizon for a profile.

    ``margin_deg`` can represent target apparent radius or safety margin.
    """
    max_obs = max_obstruction_angle(
        observer_elevation_m, profile, observer_height_m=observer_height_m
    )
    if max_obs is None:
        return HorizonObstructionResult(
            blocked=False,
            target_altitude_deg=target_altitude_deg,
            max_obstruction_angle_deg=None,
            azimuth_deg=azimuth_deg,
            profile_source=profile_source,
        )
    blocked = target_altitude_deg < (max_obs + margin_deg)
    return HorizonObstructionResult(
        blocked=blocked,
        target_altitude_deg=target_altitude_deg,
        max_obstruction_angle_deg=max_obs,
        azimuth_deg=azimuth_deg,
        profile_source=profile_source,
    )
