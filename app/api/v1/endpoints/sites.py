from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_site_service
from app.schemas.sites import (
    CoordinateSiteReference,
    Site,
    SiteListResponse,
    SiteResolveResponse,
)
from app.services.sites import SiteService

router = APIRouter(prefix="/sites", tags=["Sites"])


@router.get("", response_model=SiteListResponse)
def list_sites(
    region: str | None = Query(default=None),
    south_polar_only: bool = Query(default=False),
    service: SiteService = Depends(get_site_service),
) -> SiteListResponse:
    sites = service.list_sites(region=region, south_polar_only=south_polar_only)
    return SiteListResponse(sites=sites, total=len(sites))


@router.post("/resolve", response_model=SiteResolveResponse)
def resolve_site(
    payload: CoordinateSiteReference,
    service: SiteService = Depends(get_site_service),
) -> SiteResolveResponse:
    site = service.resolve(payload)
    return SiteResolveResponse(
        site=site,
        persisted=False,
        notes=[
            "Coordinates are normalized for this response only.",
            "Custom sites are not stored; send the coordinates with each analysis request.",
        ],
    )


@router.get("/{site_id}", response_model=Site)
def get_site(
    site_id: str,
    service: SiteService = Depends(get_site_service),
) -> Site:
    return service.get(site_id)
