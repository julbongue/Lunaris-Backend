from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.exceptions import BadRequestError, LunarisError
from app.schemas.analysis import AnalysisRequest
from app.schemas.scenarios import (
    ComparisonRequest,
    ComparisonResult,
    ScenarioInput,
    ScenarioOutcome,
)
from app.services.analysis import AnalysisService

logger = logging.getLogger(__name__)

COMPARISON_CAVEATS = [
    "Comparison reports each scenario independently; it does not compute a composite "
    "score or rank sites.",
    "All scenarios use the same geometric baseline engine. Scenario errors are reported "
    "individually and are not replaced with simulated values.",
]


class ComparisonService:
    def __init__(self, analysis_service: AnalysisService, settings: Settings) -> None:
        self._analysis_service = analysis_service
        self._settings = settings

    async def compare(self, request: ComparisonRequest) -> ComparisonResult:
        if len(request.scenarios) > self._settings.max_comparison_scenarios:
            raise BadRequestError(
                "Too many scenarios requested.",
                details={
                    "max_scenarios": self._settings.max_comparison_scenarios,
                    "requested": len(request.scenarios),
                },
            )

        semaphore = asyncio.Semaphore(2)

        async def run(scenario: ScenarioInput) -> ScenarioOutcome:
            async with semaphore:
                return await self._run_scenario(scenario)

        outcomes = await asyncio.gather(*(run(scenario) for scenario in request.scenarios))
        return ComparisonResult(
            created_at=datetime.now(UTC),
            scenarios=list(outcomes),
            caveats=list(COMPARISON_CAVEATS),
        )

    async def _run_scenario(self, scenario: ScenarioInput) -> ScenarioOutcome:
        try:
            result = await self._analysis_service.analyze(
                AnalysisRequest(
                    site=scenario.site,
                    start_time=scenario.start_time,
                    stop_time=scenario.stop_time,
                    step_minutes=scenario.step_minutes,
                    thresholds=scenario.thresholds,
                    include_samples=False,
                )
            )
            return ScenarioOutcome(
                label=scenario.label,
                status="ok",
                analysis_id=result.analysis_id,
                site=result.site,
                summary=result.summary,
                solar_windows=result.solar_windows,
                communication_windows=result.communication_windows,
                model=result.model,
            )
        except LunarisError as exc:
            return ScenarioOutcome(
                label=scenario.label,
                status="error",
                error=exc.message,
            )
        except Exception:
            logger.exception("Unexpected error while comparing scenario %s", scenario.label)
            return ScenarioOutcome(
                label=scenario.label,
                status="error",
                error="Unexpected internal error while processing this scenario.",
            )
