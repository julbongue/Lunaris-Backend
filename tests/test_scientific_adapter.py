from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import BadRequestError, EngineUnavailableError
from app.schemas.analysis import AnalysisRequest, Thresholds
from app.schemas.sites import CoordinateSiteReference
from app.services.engine.ephemeris_provider import (
    HorizonsVectorEphemerisProvider,
    MockDeterministicEphemerisProvider,
    NoopCoordinateTransformer,
)
from app.services.engine.scientific_adapter import ScientificAdapter
from app.services.sites import SiteService


def make_request(**overrides):
    payload = {
        "site": {"type": "coordinates", "latitude_deg": -89.9, "longitude_deg": 0.0},
        "start_time": "2026-11-15T00:00:00Z",
        "stop_time": "2026-11-15T03:00:00Z",
        "step_minutes": 60,
        "thresholds": {"sun_elevation_deg": 0.0, "earth_elevation_deg": 5.0},
        "include_samples": True,
        "coordinate_system": "planetocentric",
        "reference_frame": "selenographic",
        "terrain_availability": "none",
        "horizon_reference": "geometric",
    }
    payload.update(overrides)
    return AnalysisRequest(**payload)


def resolve_site(request: AnalysisRequest):
    return SiteService.from_file().resolve(request.site)


def test_mock_provider_returns_deterministic_instants():
    req = make_request()
    site = resolve_site(req)
    provider = MockDeterministicEphemerisProvider()
    times = [req.start_time + timedelta(minutes=60 * i) for i in range(3)]
    inst1 = asyncio.run(provider.get_instants(site=site, times_utc=times, reference_frame="selenographic"))
    inst2 = asyncio.run(provider.get_instants(site=site, times_utc=times, reference_frame="selenographic"))
    assert len(inst1) == 3
    assert [i.source for i in inst1] == ["mock", "mock", "mock"]
    assert [(i.sun_azimuth_deg, i.sun_elevation_deg) for i in inst1] == [
        (i.sun_azimuth_deg, i.sun_elevation_deg) for i in inst2
    ]


def test_scientific_adapter_per_instant_and_aggregation_integrity():
    req = make_request()
    site = resolve_site(req)
    adapter = ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())
    out = asyncio.run(adapter.analyze_request(req, site))
    # [start, stop) with 60min step over 3h => 3 instants
    assert len(out.instants) == 3
    assert out.summary.total_samples == 3
    assert len(out.samples_points) == 3
    assert [p.timestamp for p in out.samples_points] == [ir.timestamp for ir in out.instants]
    # Each instant has definitive EngineResult with geometric fields
    for ir in out.instants:
        assert ir.result.earth is not None
        assert ir.result.sun is not None
        assert ir.result.sun_coordinates is not None
        assert ir.result.earth_coordinates is not None
        assert ir.result.illumination is not None
        assert ir.result.conditions is not None
        assert ir.result.horizon is None
        assert 0.0 <= ir.result.illumination.phase_angle_deg <= 180.0
        assert 0.0 <= ir.result.illumination.incidence_angle_deg <= 90.0
        assert 0.0 <= ir.result.illumination.emission_angle_deg <= 90.0
        assert ir.result.conditions.insolation_w_m2 >= 0.0
    assert out.quality.engine_name == adapter.name
    assert out.quality.coordinate_system == "planetocentric"
    assert out.quality.reference_frame == "selenographic"
    assert out.quality.elevation_source == "mock"
    assert "synthetic" in " ".join(out.quality.notes).lower() or "mock" in " ".join(out.quality.notes).lower()


def test_rejects_planetographic():
    req = make_request(coordinate_system="planetographic")
    site = resolve_site(req)
    adapter = ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())
    with pytest.raises(BadRequestError) as exc:
        asyncio.run(adapter.analyze_request(req, site))
    assert exc.value.details.get("code") == "coordinate_conventions_unsupported"


def test_rejects_inertial_reference_frame():
    req = make_request(reference_frame="inertial")
    site = resolve_site(req)
    adapter = ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())
    with pytest.raises(BadRequestError) as exc:
        asyncio.run(adapter.analyze_request(req, site))
    assert exc.value.details.get("code") == "coordinate_transformation_unavailable"


def test_rejects_terrain_unavailable_modes():
    site = resolve_site(make_request())
    adapter = ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())
    for terrain in ("local", "archive"):
        req = make_request(terrain_availability=terrain)
        with pytest.raises(BadRequestError) as exc:
            asyncio.run(adapter.analyze_request(req, site))
        assert exc.value.details.get("code") == "terrain_unavailable"


def test_horizons_vector_provider_unavailable():
    req = make_request()
    site = resolve_site(req)
    provider = HorizonsVectorEphemerisProvider()
    with pytest.raises(EngineUnavailableError):
        asyncio.run(provider.get_instants(site=site, times_utc=[req.start_time], reference_frame="selenographic"))


def test_quality_notes_include_limitations_and_no_topography():
    req = make_request()
    site = resolve_site(req)
    adapter = ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())
    out = asyncio.run(adapter.analyze_request(req, site))
    notes = " ".join(out.quality.notes).lower()
    caveats = " ".join(out.caveats).lower()
    assert "spherical" in notes or "terrain" in notes
    assert "no terrain" in caveats or "geometric horizon" in caveats
    assert out.quality.elevation_source == "mock"
    assert out.instants[0].result.horizon is None
    assert out.instants[0].result.illumination is not None
    assert out.instants[0].result.conditions is not None

