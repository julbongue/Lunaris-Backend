from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_service
from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.services.analysis import AnalysisService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post("", response_model=AnalysisResult, response_model_exclude_none=True)
async def create_analysis(
    request: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResult:
    return await service.analyze(request)


@router.get(
    "/{analysis_id}",
    response_model=AnalysisResult,
    response_model_exclude_none=True,
)
def get_analysis(
    analysis_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisResult:
    return service.get(analysis_id)
