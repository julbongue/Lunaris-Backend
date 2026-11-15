from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.analysis import (
    AnalysisModel,
    AnalysisSummary,
    Thresholds,
    VisibilityWindow,
)
from app.services.types import CombinedPoint


@dataclass(frozen=True)
class EngineInput:
    points: list[CombinedPoint]
    thresholds: Thresholds
    range_start: datetime
    range_end: datetime
    step_minutes: int


@dataclass(frozen=True)
class EngineOutput:
    summary: AnalysisSummary
    solar_windows: list[VisibilityWindow]
    communication_windows: list[VisibilityWindow]
    model: AnalysisModel


class ScientificEngine(Protocol):
    """Interface for interchangeable scientific analysis engines.

    The MVP ships a transparent geometric baseline. A future SPICE/terrain
    engine can implement this protocol and be selected with
    SCIENTIFIC_ENGINE without changing the API layer.
    """

    name: str
    version: str

    def analyze(self, data: EngineInput) -> EngineOutput: ...
