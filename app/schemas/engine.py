from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Conventions
# ---------------------------------------------------------------------------

# Geographic coordinate systems for lunar sites (latitude/longitude).
# - planetocentric: latitude measured from the lunar equator plane.
# - planetographic: latitude on a rotating ellipsoid (used by some lunar
#   datum models).  The value is in degrees and must be interpreted with
#   respect to the chosen ellipsoid.
# - selenographic:  conventional lunar naming (same axes as planetocentric);
#   kept for backward compatibility with lunar cartographic literature.
CoordinateSystem = Literal["planetocentric", "planetographic", "selenographic"]

# Reference frames for the ephemeris computation.
# - selenographic:   lunar-centred, surface-fixed frame (the frame in
#   which the Moon rotates).  Topocentric directions are usually expressed
#   in this frame after rotating from the inertial frame.
# - inertial:        ICRF / J2000, non-rotating.
# - ecliptic:        ecliptic of date (oblique) frame.
ReferenceFrame = Literal["selenographic", "inertial", "ecliptic"]

# Horizon used for visibility.
ElevationReference = Literal["geometric", "topographic"]


class EngineInput(BaseModel):
    """Definitive input contract for a scientific engine.

    This schema is the authoritative input for any engine developed under
    the ``ScientificEngine`` protocol.  It carries the full observation
    context: coordinates, epoch, frame and thresholds.

    Notes on conventions
    --------------------
    * latitude_deg : geographic latitude, positive north.  The default
      ``coordinate_system`` is ``planetocentric`` (latitude measured from
      the lunar equator plane).  If ``planetographic`` is selected the
      latitude is still in degrees but must be interpreted with respect
      to the lunar reference ellipsoid.
    * longitude_deg: east-positive.  Values in [-180, 180] are
      normalised to [0, 360) by the caller before they are passed to a
      computation that expects east-positive longitude.
    * altitude_m   : height of the observer above the reference
      ellipsoid (planetographic) or sphere (planetocentric).  If the
      site dataset does not provide an elevation the value 0 m is used
      and a caveat is returned.
    * start_time   : inclusive UTC.
    * stop_time    : exclusive UTC.  The engine samples the interval
      [start, stop) with the given step.
    * step_minutes : sampling interval in minutes (1..1440).
    """

    # Geographic coordinates (lunar)
    latitude_deg: float = Field(
        ge=-90.0,
        le=90.0,
        description="Geographic latitude in degrees. Positive north.",
    )
    longitude_deg: float = Field(
        ge=-180.0,
        le=180.0,
        description="Geographic longitude in degrees, east-positive.  Values in "
        "[-180, 180] are normalised to [0, 360) by the caller.",
    )
    altitude_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Observer altitude above the reference surface in metres.  "
        "If the site dataset does not provide an elevation the value 0 m is "
        "used and a caveat is returned.",
    )

    # Observation window
    start_time: datetime = Field(description="Inclusive UTC start time.")
    stop_time: datetime = Field(description="Exclusive UTC stop time.")
    step_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="Sampling interval in minutes.",
    )

    # Coordinate / reference frame conventions
    coordinate_system: CoordinateSystem = Field(
        default="planetocentric",
        description="Coordinate system used for latitude/longitude.  "
        "planetocentric is the default and matches JPL Horizons.",
    )
    reference_frame: ReferenceFrame = Field(
        default="selenographic",
        description="Reference frame for the ephemeris computation.  "
        "selenographic is the lunar surface-fixed frame used for topocentric "
        "directions.",
    )

    # Scientific thresholds
    sun_elevation_deg: float = Field(
        default=0.0,
        ge=-90.0,
        le=90.0,
        description="Sun geometric elevation threshold for 'sunlit' samples.",
    )
    earth_elevation_deg: float = Field(
        default=5.0,
        ge=-90.0,
        le=90.0,
        description="Earth geometric elevation threshold for direct-link samples.",
    )

    # Additional parameters used by future engines
    terrain_availability: Literal["none", "local", "archive"] = Field(
        default="none",
        description="Whether local terrain data is available to compute "
        "topographic horizon obstructions.",
    )
    horizon_reference: ElevationReference = Field(
        default="geometric",
        description="Reference used to define the horizon for visibility.",
    )

    # Metadata
    source: str = Field(
        default="jpl_horizons",
        description="Identifier of the ephemeris source.",
    )

    @field_validator("start_time", "stop_time")
    @classmethod
    def _normalize_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _validate_window(self) -> EngineInput:
        if self.stop_time <= self.start_time:
            raise ValueError("stop_time must be after start_time")
        return self


EngineInput.model_rebuild()


class CelestialCoordinates(BaseModel):
    """Topocentric direction of a celestial body in the selected frame."""

    azimuth_deg: float = Field(
        ge=0.0, le=360.0, description="Azimuth in degrees, clockwise from north."
    )
    elevation_deg: float = Field(
        ge=-90.0, le=90.0, description="Geometric elevation in degrees "
        "above the local horizon."
    )
    range_km: float | None = Field(
        default=None,
        description="Topocentric range in kilometres (when available).",
    )


class EarthVisibility(BaseModel):
    """Visibility of the Earth above the selected threshold."""

    visible: bool = Field(
        description="True if the geometric elevation of the Earth is above "
        "the threshold."
    )
    elevation_deg: float = Field(
        ge=-90.0,
        le=90.0,
        description="Geometric elevation of the Earth in degrees.",
    )
    azimuth_deg: float = Field(description="Azimuth of the Earth in degrees.")
    elevation_threshold_deg: float = Field(
        description="The elevation threshold used for the visibility test."
    )


class SunVisibility(BaseModel):
    """Visibility of the Sun above the selected threshold."""

    visible: bool = Field(
        description="True if the geometric elevation of the Sun is above "
        "the threshold."
    )
    elevation_deg: float = Field(
        ge=-90.0,
        le=90.0,
        description="Geometric elevation of the Sun in degrees.",
    )
    azimuth_deg: float = Field(description="Azimuth of the Sun in degrees.")
    elevation_threshold_deg: float = Field(
        description="The elevation threshold used for the visibility test."
    )


class IlluminationAngles(BaseModel):
    """Angles that define the illumination and observing geometry.

    All angles are in degrees.  The geometry follows the standard
    selenophotometry convention: observer (O), surface point (P) and Sun (S).

    * phase_angle   : Sun-Object-Surface point angle (Sun-Earth observer
      angle for the Sun as seen from the observer).
    * incidence     : angle between the surface normal and the Sun
      direction (0 = Sun at zenith).
    * emission      : angle between the surface normal and the
      observer direction (0 = observer at zenith).
    * solar_longitude: direction of the Sun as seen by the observer,
      clockwise from north, in degrees.
    """

    phase_angle_deg: float = Field(
        ge=0.0, le=180.0, description="Sun-object-observer phase angle."
    )
    incidence_angle_deg: float = Field(
        ge=0.0, le=90.0, description="Sun-surface incidence angle."
    )
    emission_angle_deg: float = Field(
        ge=0.0, le=90.0, description="Observer-surface emission angle."
    )
    solar_longitude_deg: float = Field(
        ge=0.0, le=360.0, description="Solar azimuth seen by the observer."
    )


class IlluminationConditions(BaseModel):
    """Local illumination state."""

    sunlit: bool = Field(description="True if the local solar elevation >= 0.")
    dark: bool = Field(description="True if the local solar elevation <= 0.")
    terminator: bool = Field(
        description="True if the site is near the terminator (solar "
        "elevation close to 0)."
    )
    insolation_w_m2: float = Field(
        ge=0.0, description="Solar irradiance at the site (W/m2).  "
        "Not derived by the baseline engine; set to 0 when unavailable."
    )


class HorizonObstruction(BaseModel):
    """Local terrain horizon, when terrain data is available."""

    reference: ElevationReference = Field(
        description="Reference used to define the horizon."
    )
    horizon_elevation_deg: float = Field(
        ge=-90.0,
        le=90.0,
        description="Maximum depression of the terrain below the geometric "
        "horizon along the requested azimuth, in degrees.",
    )
    has_data: bool = Field(
        description="True if a terrain dataset was available and sampled."
    )
    source: str | None = Field(
        default=None, description="Provenance of the terrain data."
    )
    notes: list[str] = Field(
        default_factory=list, description="Diagnostic notes about the terrain sampling."
    )


class DataQualityMetadata(BaseModel):
    """Precision metadata and provenance of the computation."""

    engine_name: str = Field(description="Name of the engine implementation.")
    engine_version: str = Field(description="Version of the engine implementation.")
    coordinate_system: str = Field(
        description="Coordinate system used for latitude/longitude."
    )
    reference_frame: str = Field(description="Reference frame used for the computation.")
    elevation_source: str = Field(
        description="Source of the elevation model (e.g. LOLA, SLDEM2015)."
    )
    temporal_extent: str = Field(
        description="Time range covered by the computation (ISO 8601)."
    )
    notes: list[str] = Field(
        default_factory=list, description="Additional notes on precision or caveats."
    )


class EngineResult(BaseModel):
    """Definitive output contract for a scientific engine.

    This schema is the authoritative response of any engine that implements
    the ``ScientificEngine`` protocol.  It is intentionally richer than the
    legacy ``EngineOutput`` to cover the scientific quantities listed in the
    LUNARIS specification.
    """

    # Visibility of the two primary bodies
    earth: EarthVisibility | None = Field(
        default=None, description="Earth visibility result."
    )
    sun: SunVisibility | None = Field(
        default=None, description="Sun visibility result."
    )

    # Topocentric celestial coordinates
    sun_coordinates: CelestialCoordinates | None = Field(
        default=None, description="Topocentric Sun coordinates."
    )
    earth_coordinates: CelestialCoordinates | None = Field(
        default=None, description="Topocentric Earth coordinates."
    )

    # Illumination
    illumination: IlluminationAngles | None = Field(
        default=None, description="Illumination angles at the site."
    )
    conditions: IlluminationConditions | None = Field(
        default=None, description="Local illumination conditions."
    )

    # Terrain horizon obstruction
    horizon: HorizonObstruction | None = Field(
        default=None, description="Horizon obstruction information."
    )

    # Quality metadata
    quality: DataQualityMetadata | None = Field(
        default=None, description="Precision and provenance metadata."
    )
