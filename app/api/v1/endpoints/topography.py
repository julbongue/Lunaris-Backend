from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_site_service, get_topography_service
from app.schemas.topography import (
    TopographyContext,
    TopographyContextRequest,
    TopographyLayerList,
)
from app.services.sites import SiteService
from app.services.topography import TopographyService

router = APIRouter(prefix="/topography", tags=["Topography"])


@router.get("/layers", response_model=TopographyLayerList)
def list_layers(
    provider: str | None = Query(default=None),
    data_type: str | None = Query(default=None),
    service: TopographyService = Depends(get_topography_service),
) -> TopographyLayerList:
    return service.list_layers(provider=provider, data_type=data_type)


@router.post("/context", response_model=TopographyContext)
def get_topography_context(
    request: TopographyContextRequest,
    site_service: SiteService = Depends(get_site_service),
    service: TopographyService = Depends(get_topography_service),
) -> TopographyContext:
    site = site_service.resolve(request.site)
    return service.build_context(
        site,
        layer_id=request.layer_id,
        size_deg=request.size_deg,
    )
