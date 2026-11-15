"""Lunar coordinate representations and conversions.

Conventions
-----------
- Selenographic/planetocentric latitude ``lat``: degrees, [-90, +90], positive
  north.
- Longitude ``lon``: degrees, east-positive. Public inputs may be in [-180,180]
  or [0,360); normalized forms are documented per function.
- Radius ``r``: distance from lunar center in meters (m) unless stated.
- Mean lunar radius constant is provided for convenience but real analyses
  should use topographic radius/altitude from data sources when available.

This module treats the Moon as a sphere for basic geometric conversions unless a
specific datum/ellipsoid is introduced later. Planetographic vs planetocentric
differences are negligible for a spherical model but must be stated explicitly
when ellipsoidal models are used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .vectors import Vec3, deg_to_rad, normalize_longitude_deg, rad_to_deg, vec3

# IAU mean radius (km) ~ 1737.4; stored in meters for SI consistency in this
# module's geometric helpers. Source context: common lunar reference value.
MEAN_LUNAR_RADIUS_M = 1_737_400.0


@dataclass(frozen=True, slots=True)
class SelenographicPoint:
    """Point on/above lunar reference sphere.

    lat_deg: planetocentric latitude in degrees, north positive.
    lon_deg: east-positive longitude in degrees.
    altitude_m: height above reference radius in meters.
    radius_m: distance from lunar center in meters (derived or explicit).
    """

    lat_deg: float
    lon_deg: float
    altitude_m: float = 0.0

    @property
    def radius_m(self) -> float:
        return MEAN_LUNAR_RADIUS_M + self.altitude_m


def selenographic_to_cartesian(
    lat_deg: float,
    lon_deg: float,
    radius_m: float,
) -> Vec3:
    """Convert selenographic/planetocentric spherical coordinates to Cartesian.

    Axes (body-fixed, right-handed, spherical convention used here):
    - x: intersection of equator and prime meridian (lon=0, lat=0)
    - y: equator at lon=+90°E
    - z: north pole (lat=+90°)

    Returns vector in meters from lunar center.
    """
    lat = deg_to_rad(lat_deg)
    lon = deg_to_rad(lon_deg)
    clat = math.cos(lat)
    x = radius_m * clat * math.cos(lon)
    y = radius_m * clat * math.sin(lon)
    z = radius_m * math.sin(lat)
    return vec3(x, y, z)


def cartesian_to_selenographic(v: Vec3) -> tuple[float, float, float]:
    """Convert Cartesian vector (meters) to (lat_deg, lon_deg_east, radius_m)."""
    r = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if r == 0:
        raise ValueError("Cannot convert zero vector to selenographic coordinates")
    lat = math.asin(max(-1.0, min(1.0, v.z / r)))
    lon = math.atan2(v.y, v.x)
    lat_deg = rad_to_deg(lat)
    lon_deg = normalize_longitude_deg(rad_to_deg(lon))
    return (lat_deg, lon_deg, r)


def surface_normal_planetocentric(lat_deg: float, lon_deg: float) -> Vec3:
    """Outward radial unit normal for a spherical Moon at given location."""
    v = selenographic_to_cartesian(lat_deg, lon_deg, 1.0)
    n = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    return vec3(v.x / n, v.y / n, v.z / n)
