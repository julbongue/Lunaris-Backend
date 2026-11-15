"""Solar geometry and surface illumination conditions.

Illumination here refers to **direct geometric illumination** from the Sun based
on direction/angles. It does not model diffuse lighting, Earthshine, thermal
emission, or terrain occlusion except where explicitly combined with topography.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .celestial import apparent_position_from_observer
from .coordinates import selenographic_to_cartesian, surface_normal_planetocentric
from .frames import local_frame
from .vectors import Vec3, angle_between_deg, normalize
from .visibility import ObserverLocation


@dataclass(frozen=True, slots=True)
class SolarGeometryResult:
    azimuth_deg: float
    altitude_deg: float
    distance_km: Optional[float]
    incidence_angle_deg: float  # angle between Sun direction and local normal
    emission_angle_deg: float | None  # angle between Earth/view direction and local normal
    phase_angle_deg: float | None  # angle between Sun and Earth directions at surface
    solar_longitude_deg: float  # solar azimuth (deg)
    surface_normal_body: Vec3
    sun_direction_body: Vec3
    earth_direction_body: Vec3 | None
    directly_illuminated: bool
    illumination_condition: str  # "daylight", "twilight_geometric", "night", etc.


def solar_geometry(
    observer: ObserverLocation,
    sun_position_body_km: Vec3,
    *,
    earth_position_body_km: Vec3 | None = None,
    surface_normal_body: Optional[Vec3] = None,
    min_sun_altitude_deg: float = 0.0,
) -> SolarGeometryResult:
    """Compute apparent Sun position and local incidence/illumination.

    Parameters
    ----------
    sun_position_body_km:
        Sun position vector in same body-fixed frame (km), from external ephemeris.
    earth_position_body_km:
        Optional Earth position vector for emission/phase geometry.
    surface_normal_body:
        Local terrain/surface normal in body-fixed frame. Defaults to
        planetocentric radial normal (smooth sphere).
    """
    r_km = observer.effective_radius_m / 1000.0
    obs_pos_km = selenographic_to_cartesian(observer.lat_deg, observer.lon_deg, r_km)
    frame = local_frame(observer.lat_deg, observer.lon_deg, r_km)
    apparent = apparent_position_from_observer(obs_pos_km, sun_position_body_km, frame)

    n = (
        normalize(surface_normal_body)
        if surface_normal_body is not None
        else surface_normal_planetocentric(observer.lat_deg, observer.lon_deg)
    )
    sun_dir = apparent.direction_body
    incidence = angle_between_deg(sun_dir, n)

    earth_dir = None
    emission = None
    phase = None
    if earth_position_body_km is not None:
        earth_app = apparent_position_from_observer(obs_pos_km, earth_position_body_km, frame)
        earth_dir = earth_app.direction_body
        emission = angle_between_deg(earth_dir, n)
        phase = angle_between_deg(sun_dir, earth_dir)

    above_horizon = apparent.altitude_deg >= min_sun_altitude_deg
    facing_sun = incidence < 90.0
    illuminated = above_horizon and facing_sun
    if illuminated:
        condition = "daylight_direct"
    elif above_horizon and not facing_sun:
        condition = "above_horizon_not_facing_sun"
    elif apparent.altitude_deg >= -0.833:
        condition = "horizon_grazing_or_below"
    else:
        condition = "night"

    return SolarGeometryResult(
        azimuth_deg=apparent.azimuth_deg,
        altitude_deg=apparent.altitude_deg,
        distance_km=apparent.distance_km,
        incidence_angle_deg=incidence,
        emission_angle_deg=emission,
        phase_angle_deg=phase,
        solar_longitude_deg=apparent.azimuth_deg % 360.0,
        surface_normal_body=n,
        sun_direction_body=sun_dir,
        earth_direction_body=earth_dir,
        directly_illuminated=illuminated,
        illumination_condition=condition,
    )
