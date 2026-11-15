from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_source_service
from app.schemas.sources import SourceListResponse
from app.services.sources import SourceService

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=SourceListResponse)
def list_sources(
    service: SourceService = Depends(get_source_service),
) -> SourceListResponse:
    return service.list_sources()
