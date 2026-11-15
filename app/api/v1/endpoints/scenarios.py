from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_comparison_service
from app.schemas.scenarios import ComparisonRequest, ComparisonResult
from app.services.comparison import ComparisonService

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


@router.post(
    "/compare",
    response_model=ComparisonResult,
    response_model_exclude_none=True,
)
async def compare_scenarios(
    request: ComparisonRequest,
    service: ComparisonService = Depends(get_comparison_service),
) -> ComparisonResult:
    return await service.compare(request)
