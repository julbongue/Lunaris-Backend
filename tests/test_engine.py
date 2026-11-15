from datetime import UTC, datetime, timedelta

from app.schemas.analysis import Thresholds
from app.services.engine.base import EngineInput
from app.services.engine.geometric import GeometricEngine
from app.services.types import CombinedPoint

START = datetime(2026, 11, 15, tzinfo=UTC)


def _point(index: int, sun: float, earth: float) -> CombinedPoint:
    return CombinedPoint(
        timestamp=START + timedelta(hours=index),
        sun_azimuth_deg=100.0,
        sun_elevation_deg=sun,
        earth_azimuth_deg=200.0,
        earth_elevation_deg=earth,
    )


def test_geometric_engine_builds_sampled_windows():
    points = [
        _point(0, -5.0, -5.0),
        _point(1, 5.0, 5.0),
        _point(2, 5.0, -5.0),
        _point(3, 5.0, 5.0),
    ]
    output = GeometricEngine().analyze(
        EngineInput(
            points=points,
            thresholds=Thresholds(sun_elevation_deg=0.0, earth_elevation_deg=0.0),
            range_start=points[0].timestamp,
            range_end=points[-1].timestamp,
            step_minutes=60,
        )
    )

    assert output.summary.total_samples == 4
    assert output.summary.sun_above_threshold_pct == 75.0
    assert output.summary.earth_above_threshold_pct == 50.0
    assert len(output.solar_windows) == 1
    assert output.solar_windows[0].start_time == START + timedelta(hours=1)
    assert output.solar_windows[0].end_time == START + timedelta(hours=3)
    assert output.solar_windows[0].duration_minutes == 120.0
    assert output.solar_windows[0].sample_count == 3
    assert output.solar_windows[0].ends_at_range_boundary is True
    assert len(output.communication_windows) == 2
    assert output.communication_windows[0].duration_minutes == 0.0
    assert output.communication_windows[0].sample_count == 1

    assert output.model.name == "geometric-altaz-threshold"
    assert any("terrain" in limitation.lower() for limitation in output.model.limitations)


def test_geometric_engine_marks_boundary_windows():
    points = [_point(0, 5.0, 5.0), _point(1, 5.0, 5.0)]
    output = GeometricEngine().analyze(
        EngineInput(
            points=points,
            thresholds=Thresholds(sun_elevation_deg=0.0, earth_elevation_deg=0.0),
            range_start=points[0].timestamp,
            range_end=points[-1].timestamp,
            step_minutes=60,
        )
    )

    window = output.solar_windows[0]
    assert window.starts_at_range_boundary is True
    assert window.ends_at_range_boundary is True
