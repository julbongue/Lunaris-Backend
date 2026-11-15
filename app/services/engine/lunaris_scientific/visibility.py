"""Geometric visibility of celestial bodies from a lunar observer.

Distinguishes:
- **Geometric visibility**: target above local geometric horizon (altitude > 0°)
  in the chosen reference model, without terrain occlusion.
- **Topographic visibility**: geometric visibility AND not blocked by terrain
  profile (handled with `topography` module).

This module implements geometric checks only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .celestial import ApparentPosition, apparent_position_from_observer
from .coordinates import MEAN_LUNAR_RADIUS_M, selenographic_to_cartesian
from .frames import local_frame
from .vectors import Vec3


@dataclass(frozen=True, slots=True)
class ObserverLocation:
    lat_deg: float
    lon_deg: float
    altitude_m: float = 0.0
    radius_m: Optional[float] = None  # if None uses mean radius + altitude_m

    @property
    def effective_radius_m(self) -> float:
        return self.radius_m if self.radius_m is not None else MEAN_LUNAR_RADIUS_M + self.altitude_m


@dataclass(frozen=True, slots=True)
class GeometricVisibilityResult:
    visible: bool
    azimuth_deg: float
    elevation_deg: float
    distance_km: Optional[float]
    observer_vector_body_km: Vec3
    target_vector_body_km: Vec3
    target_direction_body: Vec3
    horizon_reference: str = "geometric"


def earth_visibility_geometric(
    observer: ObserverLocation,
    earth_position_body_km: Vec3,
    *,
    min_elevation_deg: float = 0.0,
) -> GeometricVisibilityResult:
    """Compute geometric Earth visibility from a lunar surface point.

    Parameters
    ----------
    earth_position_body_km:
        Earth position vector in the same body-fixed frame as observer frame
        (kilometers). Must come from external ephemeris; not invented.
    min_elevation_deg:
        Threshold for visibility (default 0° = geometric horizon).
    """
    r_km = observer.effective_radius_m / 1000.0
    obs_pos_km = selenographic_to_cartesian(observer.lat_deg, observer.lon_deg, r_km)
    frame = local_frame(observer.lat_deg, observer.lon_deg, r_km)
    apparent = apparent_position_from_observer(obs_pos_km, earth_position_body_km, frame)
    visible = apparent.altitude_deg >= min_elevation_deg
    return GeometricVisibilityResult(
        visible=visible,
        azimuth_deg=apparent.azimuth_deg,
        elevation_deg=apparent.altitude_deg,
        distance_km=apparent.distance_km,
        observer_vector_body_km=obs_pos_km,
        target_vector_body_km=earth_position_body_km,
        target_direction_body=apparent.direction_body,
    )
