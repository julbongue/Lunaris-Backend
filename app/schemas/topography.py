from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.sites import Site, SiteReference


class TopographyLayer(ApiModel):
    id: str
    provider: Literal["lroc_wms", "moontrek_wmts"]
    layer_id: str
    title: str
    description: str
    data_type: Literal["basemap", "imagery", "dem", "illumination", "hazard"]
    resolution_m_per_px: float | None = None
    access: Literal["wms", "wmts"]
    service_url: str
    capabilities_url: str | None = None
    tile_url_template: str | None = None
    attribution: str
    source_url: str
    notes: str | None = None


class TopographyLayerList(ApiModel):
    layers: list[TopographyLayer]
    total: int
    caveats: list[str] = Field(default_factory=list)


class TopographyContextRequest(ApiModel):
    site: SiteReference
    layer_id: str = "lroc-wac-global"
    size_deg: float = Field(default=0.5, ge=0.01, le=10.0)


class BoundingBox(ApiModel):
    min_latitude_deg: float
    min_longitude_deg: float
    max_latitude_deg: float
    max_longitude_deg: float


class TopographyContext(ApiModel):
    site: Site
    layer: TopographyLayer
    bbox: BoundingBox
    map_url: str | None = None
    tile_url_template: str | None = None
    capabilities_url: str | None = None
    elevation_m: float | None = None
    elevation_available: bool
    elevation_source: str | None = None
    notes: list[str] = Field(default_factory=list)
