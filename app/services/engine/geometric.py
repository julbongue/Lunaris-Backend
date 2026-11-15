from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from app.schemas.analysis import (
    AnalysisModel,
    AnalysisSummary,
    VisibilityWindow,
)
from app.services.engine.base import EngineInput, EngineOutput
from app.services.types import CombinedPoint

LIMITATIONS = [
    "Visibility is inferred from sampled geometric elevation angles, not from "
    "terrain horizon models or shadow ray tracing.",
    "No power generation, battery, thermal, or communication link-budget model is applied.",
    "Window boundaries are sample times. Actual rise/set instants may fall between samples.",
    "Site elevation is assumed to be 0 km when the site dataset or request does not provide one.",
    "These results are preliminary and must not be used for mission-critical decisions.",
]


class GeometricEngine:
    """Transparent MVP baseline: threshold the sampled Sun/Earth elevation."""

    name = "geometric-altaz-threshold"
    version = "0.1.0"

    def analyze(self, data: EngineInput) -> EngineOutput:
        if not data.points:
            raise ValueError("At least one ephemeris sample is required")

        solar_windows = self._windows(
            data.points,
            predicate=lambda point: point.sun_elevation_deg >= data.thresholds.sun_elevation_deg,
            kind="solar",
            threshold_deg=data.thresholds.sun_elevation_deg,
            step_minutes=data.step_minutes,
            range_start=data.range_start,
            range_end=data.range_end,
        )
        communication_windows = self._windows(
            data.points,
            predicate=lambda point: (
                point.earth_elevation_deg >= data.thresholds.earth_elevation_deg
            ),
            kind="earth_communication",
            threshold_deg=data.thresholds.earth_elevation_deg,
            step_minutes=data.step_minutes,
            range_start=data.range_start,
            range_end=data.range_end,
        )

        sun_above_count = sum(
            point.sun_elevation_deg >= data.thresholds.sun_elevation_deg for point in data.points
        )
        earth_above_count = sum(
            point.earth_elevation_deg >= data.thresholds.earth_elevation_deg
            for point in data.points
        )
        total = len(data.points)

        summary = AnalysisSummary(
            total_samples=total,
            interval_minutes=data.step_minutes,
            start_time=data.range_start,
            stop_time=data.range_end,
            sun_above_threshold_pct=round(100.0 * sun_above_count / total, 2),
            earth_above_threshold_pct=round(100.0 * earth_above_count / total, 2),
            solar_window_count=len(solar_windows),
            communication_window_count=len(communication_windows),
            longest_solar_window_minutes=max(
                (window.duration_minutes for window in solar_windows), default=0.0
            ),
            longest_communication_window_minutes=max(
                (window.duration_minutes for window in communication_windows),
                default=0.0,
            ),
            sampled_sunlight_minutes=float(sun_above_count * data.step_minutes),
            sampled_earth_visibility_minutes=float(earth_above_count * data.step_minutes),
        )

        return EngineOutput(
            summary=summary,
            solar_windows=solar_windows,
            communication_windows=communication_windows,
            model=AnalysisModel(
                name=self.name,
                version=self.version,
                description=(
                    "Baseline geometric model using JPL Horizons topocentric Sun and "
                    "Earth altitude/azimuth samples. A sample is marked visible when "
                    "its elevation is at or above the configured threshold."
                ),
                limitations=list(LIMITATIONS),
            ),
        )

    @staticmethod
    def _windows(
        points: list[CombinedPoint],
        *,
        predicate: Callable[[CombinedPoint], bool],
        kind: Literal["solar", "earth_communication"],
        threshold_deg: float,
        step_minutes: int,
        range_start: datetime,
        range_end: datetime,
    ) -> list[VisibilityWindow]:
        windows: list[VisibilityWindow] = []
        current_start: datetime | None = None
        current_end: datetime | None = None
        current_count = 0

        def close_window() -> None:
            nonlocal current_start, current_end, current_count
            if current_start is None or current_end is None:
                return
            duration = (current_end - current_start).total_seconds() / 60.0
            windows.append(
                VisibilityWindow(
                    kind=kind,
                    start_time=current_start,
                    end_time=current_end,
                    duration_minutes=round(duration, 2),
                    sample_count=current_count,
                    threshold_deg=threshold_deg,
                    starts_at_range_boundary=current_start == range_start,
                    ends_at_range_boundary=current_end == range_end,
                )
            )
            current_start = None
            current_end = None
            current_count = 0

        for point in points:
            if predicate(point):
                if current_start is None:
                    current_start = point.timestamp
                current_end = point.timestamp
                current_count += 1
            else:
                close_window()

        close_window()
        return windows
