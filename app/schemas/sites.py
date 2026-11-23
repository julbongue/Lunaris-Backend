from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, HttpUrl, field_validator, model_validator

from app.core.identifiers import normalize_identifier, slugify_identifier
from app.schemas.common import ApiModel


class CoordinatesInput(ApiModel):
    name: str | None = Field(default=None, max_length=120)
    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(
        ge=-180.0,
        le=180.0,
        description="East-positive longitude. Negative values are west.",
    )
    elevation_m: float | None = Field(default=None, ge=-12000.0, le=12000.0)


class KnownSiteReference(ApiModel):
    type: Literal["known"] = "known"
    site_id: str = Field(min_length=1, max_length=100)


class CoordinateSiteReference(CoordinatesInput):
    type: Literal["coordinates"] = "coordinates"


SiteReference = Annotated[
    KnownSiteReference | CoordinateSiteReference,
    Field(discriminator="type"),
]


class Site(ApiModel):
    id: str
    name: str
    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(ge=-180.0, le=180.0)
    longitude_east_deg: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description="East-positive longitude in the 0-360 convention used by JPL Horizons.",
    )
    elevation_m: float | None = None
    region: str
    site_type: str
    mission: str | None = None
    country: str | None = None
    description: str
    source_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list)
    coordinate_precision_deg: float | None = Field(default=None, ge=0.0)
    is_south_polar: bool = False
    is_custom: bool = False

    @model_validator(mode="after")
    def _derive_fields(self) -> Site:
        self.longitude_east_deg = self.longitude_deg % 360.0
        self.is_south_polar = self.latitude_deg <= -60.0
        return self


class DatabaseSite(ApiModel):
    """A lunar site as stored in the PostgreSQL ``lunar_sites`` table."""

    id: str = Field(
        default="",
        description=(
            "Stable, URL-safe identifier derived from the name. The table has no "
            "dedicated ID column, so the API exposes this deterministic slug."
        ),
    )
    name: str
    latitude_deg: float = Field(ge=-90.0, le=90.0)
    longitude_deg: float = Field(ge=-180.0, le=180.0)
    longitude_east_deg: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description="East-positive longitude in the 0-360 convention used by JPL Horizons.",
    )
    elevation_m: float | None = None
    science_score: float | None = None
    description: str | None = None
    source: str | None = None
    is_south_polar: bool = False

    @model_validator(mode="after")
    def _derive_fields(self) -> DatabaseSite:
        if not self.id:
            self.id = slugify_identifier(self.name)
        self.longitude_east_deg = self.longitude_deg % 360.0
        self.is_south_polar = self.latitude_deg <= -60.0
        return self


class SiteListResponse(ApiModel):
    sites: list[Site]
    total: int


class DatabaseSiteListResponse(ApiModel):
    sites: list[DatabaseSite]
    total: int
    table: str
    source: str = "postgresql"


SiteIdentifier = Annotated[str, Field(min_length=1, max_length=120)]


class SiteComparisonRequest(ApiModel):
    """Identifiers of the lunar sites to compare.

    The canonical field is ``sites``.  ``site_ids``, ``site_names`` and
    ``identifiers`` are accepted as aliases so the frontend can use whichever
    name is more natural.  A raw JSON array of strings is also accepted.
    """

    sites: list[SiteIdentifier] = Field(
        min_length=1,
        max_length=20,
        validation_alias=AliasChoices(
            "sites",
            "site_ids",
            "site_names",
            "site_identifiers",
            "identifiers",
            "ids",
            "names",
        ),
        description=("Database names, URL-safe IDs or slugs of lunar sites stored in PostgreSQL."),
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_raw_list(cls, value: object) -> object:
        if isinstance(value, list):
            return {"sites": value}
        return value

    @field_validator("sites")
    @classmethod
    def _validate_identifiers(cls, value: list[str]) -> list[str]:
        normalized = [normalize_identifier(identifier) for identifier in value]
        if any(not identifier for identifier in normalized):
            raise ValueError("site identifiers must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("site identifiers must be unique")
        return value


class ComparedSite(DatabaseSite):
    requested_identifier: str = Field(
        description="The name or ID exactly as supplied in the request."
    )


class ElevationExtreme(ApiModel):
    site_id: str
    site_name: str
    elevation_m: float


class ElevationComparison(ApiModel):
    has_data: bool
    lowest: ElevationExtreme | None = None
    highest: ElevationExtreme | None = None
    difference_m: float | None = Field(
        default=None,
        description="Highest elevation minus lowest elevation, in metres.",
    )


class ScienceScoreExtreme(ApiModel):
    site_id: str
    site_name: str
    science_score: float


class ScienceScoreComparison(ApiModel):
    has_data: bool
    highest: ScienceScoreExtreme | None = None
    lowest: ScienceScoreExtreme | None = None
    difference: float | None = Field(
        default=None,
        description="Highest science score minus lowest science score.",
    )
    average: float | None = None


class SiteComparisonRow(ApiModel):
    rank: int | None = Field(
        default=None,
        description="Rank based on science score, with south-polar and elevation tie-breakers.",
    )
    site_id: str
    site_name: str
    requested_identifier: str
    latitude_deg: float
    longitude_deg: float
    longitude_east_deg: float
    is_south_polar: bool
    elevation_m: float | None = None
    elevation_difference_from_lowest_m: float | None = Field(
        default=None,
        description="Elevation minus the lowest elevation in the comparison.",
    )
    science_score: float | None = None
    science_score_difference_from_best: float | None = Field(
        default=None,
        description="Science score minus the best science score in the comparison.",
    )


class SiteRecommendation(ApiModel):
    site_id: str
    site_name: str
    reason: str
    criteria: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    science_score: float | None = None
    elevation_m: float | None = None
    runner_up_site_name: str | None = None
    science_score_gap: float | None = None


class SiteComparisonResponse(ApiModel):
    created_at: datetime
    table: str
    source: str = "postgresql"
    requested_identifiers: list[str]
    sites: list[ComparedSite]
    missing: list[str] = Field(default_factory=list)
    matrix: list[SiteComparisonRow]
    elevation_comparison: ElevationComparison
    science_score_comparison: ScienceScoreComparison
    elevation_difference_m: float | None = None
    science_score_difference: float | None = None
    best_site: ComparedSite
    recommendation: SiteRecommendation
    recommendation_text: str
    caveats: list[str] = Field(default_factory=list)


class SiteResolveResponse(ApiModel):
    site: Site
    persisted: bool = False
    notes: list[str] = Field(default_factory=list)
