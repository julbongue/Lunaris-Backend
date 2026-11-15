from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.analysis import (
    AnalysisModel,
    AnalysisSummary,
    Thresholds,
    VisibilityWindow,
)
from app.schemas.common import ApiModel, TimeRange
from app.schemas.sites import Site, SiteReference


class ScenarioInput(TimeRange):
    label: str = Field(min_length=1, max_length=80)
    site: SiteReference
    thresholds: Thresholds = Field(default_factory=Thresholds)


class ComparisonRequest(ApiModel):
    scenarios: list[ScenarioInput] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def _validate_labels(self) -> ComparisonRequest:
        labels = [scenario.label.strip().lower() for scenario in self.scenarios]
        if len(labels) != len(set(labels)):
            raise ValueError("scenario labels must be unique")
        return self


class ScenarioOutcome(ApiModel):
    label: str
    status: Literal["ok", "error"]
    analysis_id: str | None = None
    site: Site | None = None
    summary: AnalysisSummary | None = None
    solar_windows: list[VisibilityWindow] = Field(default_factory=list)
    communication_windows: list[VisibilityWindow] = Field(default_factory=list)
    model: AnalysisModel | None = None
    error: str | None = None


class ComparisonResult(ApiModel):
    created_at: datetime
    scenarios: list[ScenarioOutcome]
    caveats: list[str] = Field(default_factory=list)
