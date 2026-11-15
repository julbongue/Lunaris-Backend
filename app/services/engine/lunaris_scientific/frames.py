"""Reference frames and local observer frame construction.

Conventions
-----------
- Body-fixed Cartesian axes match ``coordinates.selenographic_to_cartesian``:
  x through (lat=0,lon=0), y through (lat=0,lon=90E), z through north pole.
- Local topocentric frame at observer (North, East, Up):
  - Up: outward radial unit normal (planetocentric/spherical).
  - East: unit vector tangent to parallel, toward increasing east longitude.
  - North: unit vector tangent to meridian, toward increasing latitude.

Horizontal coordinates:
- Azimuth: degrees clockwise from North, range [0, 360).
- Altitude (elevation angle): degrees above local horizon, [-90, +90].
- Zenith angle = 90° - altitude.

This is a geometric local frame on a spherical reference; topographic horizon
and terrain normals are handled separately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .vectors import Vec3, cross, dot, normalize, rad_to_deg, vec3


@dataclass(frozen=True, slots=True)
class LocalFrame:
    """Orthonormal local tangent frame at observer."""

    origin: Vec3  # observer position in body-fixed Cartesian (m)
    north: Vec3
    east: Vec3
    up: Vec3


def local_frame(lat_deg: float, lon_deg: float, radius_m: float) -> LocalFrame:
    """Construct local North-East-Up frame at given selenographic position."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    slat, clat = math.sin(lat), math.cos(lat)
    slon, clon = math.sin(lon), math.cos(lon)

    # Up (radial)
    up = vec3(clat * clon, clat * slon, slat)
    # East (d/dlon, normalized)
    east = vec3(-slon, clon, 0.0)
    # North (d/dlat)
    north = vec3(-slat * clon, -slat * slon, clat)

    origin = vec3(radius_m * up.x, radius_m * up.y, radius_m * up.z)
    return LocalFrame(origin=origin, north=north, east=east, up=up)


def direction_to_horizontal(frame: LocalFrame, direction_body: Vec3) -> tuple[float, float]:
    """Convert a direction vector in body-fixed frame to (azimuth_deg, altitude_deg).

    ``direction_body`` may be a position delta or absolute direction; only its
    orientation matters.
    """
    d = normalize(direction_body)
    d_n = dot(d, frame.north)
    d_e = dot(d, frame.east)
    d_u = dot(d, frame.up)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, d_u))))
    az = math.degrees(math.atan2(d_e, d_n)) % 360.0
    return (az, alt)


def horizontal_to_direction(frame: LocalFrame, azimuth_deg: float, altitude_deg: float) -> Vec3:
    """Convert horizontal coordinates to unit direction in body-fixed frame."""
    az = math.radians(azimuth_deg)
    alt = math.radians(altitude_deg)
    c_alt = math.cos(alt)
    d_n = c_alt * math.cos(az)
    d_e = c_alt * math.sin(az)
    d_u = math.sin(alt)
    # d = d_n*north + d_e*east + d_u*up
    return vec3(
        d_n * frame.north.x + d_e * frame.east.x + d_u * frame.up.x,
        d_n * frame.north.y + d_e * frame.east.y + d_u * frame.up.y,
        d_n * frame.north.z + d_e * frame.east.z + d_u * frame.up.z,
    )


def body_vector_to_local(frame: LocalFrame, v_body: Vec3) -> tuple[float, float, float]:
    """Project body-fixed vector components into (north, east, up)."""
    return (dot(v_body, frame.north), dot(v_body, frame.east), dot(v_body, frame.up))
