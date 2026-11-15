from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, TimeRange
from app.schemas.engine import (
    CelestialCoordinates,
    DataQualityMetadata,
    EarthVisibility,
    ElevationReference,
    HorizonObstruction,
    IlluminationAngles,
    IlluminationConditions,
    ReferenceFrame,
    SunVisibility,
)
from app.schemas.sites import Site, SiteReference


class Thresholds(ApiModel):
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


class AnalysisRequest(TimeRange):
    site: SiteReference
    thresholds: Thresholds = Field(default_factory=Thresholds)
    include_samples: bool = True
    coordinate_system: str = Field(default="planetocentric")
    reference_frame: ReferenceFrame = Field(default="selenographic")
    terrain_availability: Literal["none", "local", "archive"] = Field(default="none")
    horizon_reference: ElevationReference = Field(default="geometric")


class EphemerisSample(ApiModel):
    timestamp: datetime
    sun_azimuth_deg: float
    sun_elevation_deg: float
    sun_above_threshold: bool
    earth_azimuth_deg: float
    earth_elevation_deg: float
    earth_above_threshold: bool


class VisibilityWindow(ApiModel):
    kind: Literal["solar", "earth_communication"]
    start_time: datetime
    end_time: datetime
    duration_minutes: float = Field(ge=0.0)
    sample_count: int = Field(ge=1)
    threshold_deg: float
    starts_at_range_boundary: bool
    ends_at_range_boundary: bool


class AnalysisSummary(ApiModel):
    total_samples: int = Field(ge=1)
    interval_minutes: int = Field(ge=1)
    start_time: datetime
    stop_time: datetime
    sun_above_threshold_pct: float = Field(ge=0.0, le=100.0)
    earth_above_threshold_pct: float = Field(ge=0.0, le=100.0)
    solar_window_count: int = Field(ge=0)
    communication_window_count: int = Field(ge=0)
    longest_solar_window_minutes: float = Field(ge=0.0)
    longest_communication_window_minutes: float = Field(ge=0.0)
    sampled_sunlight_minutes: float = Field(ge=0.0)
    sampled_earth_visibility_minutes: float = Field(ge=0.0)


class AnalysisModel(ApiModel):
    name: str
    version: str
    description: str
    limitations: list[str] = Field(default_factory=list)


class SourceReference(ApiModel):
    name: str
    url: str
    description: str


class AnalysisResult(ApiModel):
    analysis_id: str
    created_at: datetime
    site: Site
    time_range: TimeRange
    thresholds: Thresholds
    summary: AnalysisSummary
    solar_windows: list[VisibilityWindow]
    communication_windows: list[VisibilityWindow]
    samples: list[EphemerisSample] | None = None
    model: AnalysisModel
    sources: list[SourceReference]
    caveats: list[str]
    # Optional definitive scientific fields (additive, per contract evolution)
    earth: EarthVisibility | None = None
    sun: SunVisibility | None = None
    sun_coordinates: CelestialCoordinates | None = None
    earth_coordinates: CelestialCoordinates | None = None
    illumination: IlluminationAngles | None = None
    conditions: IlluminationConditions | None = None
    horizon: HorizonObstruction | None = None
    quality: DataQualityMetadata | None = None
