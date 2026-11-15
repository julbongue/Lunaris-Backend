from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_scientific_engine
from app.main import app
from app.services.engine.ephemeris_provider import MockDeterministicEphemerisProvider
from app.services.engine.scientific_adapter import ScientificAdapter


def test_api_analysis_with_scientific_engine_mock():
    def override_engine():
        return ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())

    app.dependency_overrides[get_scientific_engine] = override_engine
    try:
        client = TestClient(app)
        req = {
            "site": {"type": "coordinates", "latitude_deg": -89.9, "longitude_deg": 0.0},
            "start_time": "2026-11-15T00:00:00Z",
            "stop_time": "2026-11-15T03:00:00Z",
            "step_minutes": 60,
            "thresholds": {"sun_elevation_deg": 0.0, "earth_elevation_deg": 5.0},
            "include_samples": True,
            "reference_frame": "selenographic",
            "terrain_availability": "none",
            "horizon_reference": "geometric",
        }
        resp = client.post("/api/v1/analysis", json=req)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["model"]["name"] == "scientific-lunaris"
        assert data["summary"]["total_samples"] == 3
        assert len(data.get("samples") or []) == 3
        assert data["quality"]["engine_name"] == "scientific-lunaris"
        assert data["quality"]["elevation_source"] == "mock"
        assert data.get("horizon") is None
        assert data.get("illumination") is not None
        assert data.get("conditions") is not None
        # representative instant fields present
        assert data.get("earth") is not None
        assert data.get("sun") is not None
        assert "no terrain" in " ".join(data.get("caveats", [])).lower() or "geometric horizon" in " ".join(data.get("caveats", [])).lower()
    finally:
        app.dependency_overrides.pop(get_scientific_engine, None)


def test_api_rejects_unsupported_reference_frame_scientific():
    def override_engine():
        return ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())

    app.dependency_overrides[get_scientific_engine] = override_engine
    try:
        client = TestClient(app)
        req = {
            "site": {"type": "coordinates", "latitude_deg": 0.0, "longitude_deg": 0.0},
            "start_time": "2026-11-15T00:00:00Z",
            "stop_time": "2026-11-15T01:00:00Z",
            "step_minutes": 60,
            "reference_frame": "inertial",
        }
        resp = client.post("/api/v1/analysis", json=req)
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["details"].get("code") == "coordinate_transformation_unavailable"
    finally:
        app.dependency_overrides.pop(get_scientific_engine, None)
