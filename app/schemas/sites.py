from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, HttpUrl, model_validator

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


class SiteListResponse(ApiModel):
    sites: list[Site]
    total: int


class SiteResolveResponse(ApiModel):
    site: Site
    persisted: bool = False
    notes: list[str] = Field(default_factory=list)
