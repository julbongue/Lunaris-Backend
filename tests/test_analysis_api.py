from fastapi.testclient import TestClient

ANALYSIS_REQUEST = {
    "site": {"type": "known", "site_id": "shackleton-rim"},
    "start_time": "2026-11-15T00:00:00Z",
    "stop_time": "2026-11-17T00:00:00Z",
    "step_minutes": 360,
    "thresholds": {"sun_elevation_deg": 0.0, "earth_elevation_deg": 5.0},
    "include_samples": True,
}


def test_create_analysis(client: TestClient):
    response = client.post("/api/v1/analysis", json=ANALYSIS_REQUEST)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["analysis_id"]
    assert payload["site"]["id"] == "shackleton-rim"
    assert payload["summary"]["total_samples"] == 9
    assert payload["summary"]["sun_above_threshold_pct"] == 66.67
    assert payload["summary"]["earth_above_threshold_pct"] == 55.56
    assert len(payload["solar_windows"]) == 3
    assert len(payload["communication_windows"]) == 5
    assert len(payload["samples"]) == 9
    assert payload["samples"][0]["sun_above_threshold"] is False
    assert payload["model"]["name"] == "geometric-altaz-threshold"
    assert payload["sources"][0]["name"] == "JPL Horizons"
    assert any("terrain" in caveat.lower() for caveat in payload["caveats"])


def test_get_cached_analysis(client: TestClient):
    created = client.post("/api/v1/analysis", json=ANALYSIS_REQUEST).json()

    response = client.get(f"/api/v1/analysis/{created['analysis_id']}")

    assert response.status_code == 200
    assert response.json()["analysis_id"] == created["analysis_id"]
    assert response.json()["summary"] == created["summary"]


def test_get_unknown_analysis_returns_404(client: TestClient):
    response = client.get("/api/v1/analysis/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_analysis_without_samples_omits_samples(client: TestClient):
    request = {**ANALYSIS_REQUEST, "include_samples": False}
    response = client.post("/api/v1/analysis", json=request)

    assert response.status_code == 200
    assert "samples" not in response.json()


def test_custom_coordinates_analysis(client: TestClient):
    request = {
        **ANALYSIS_REQUEST,
        "site": {
            "type": "coordinates",
            "name": "Custom polar site",
            "latitude_deg": -88.0,
            "longitude_deg": 15.0,
            "elevation_m": 500.0,
        },
    }
    response = client.post("/api/v1/analysis", json=request)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["site"]["is_custom"] is True
    assert payload["site"]["longitude_east_deg"] == 15.0
    assert payload["site"]["elevation_m"] == 500.0


def test_invalid_time_range_returns_422(client: TestClient):
    request = {
        **ANALYSIS_REQUEST,
        "start_time": "2026-11-17T00:00:00Z",
        "stop_time": "2026-11-15T00:00:00Z",
    }
    response = client.post("/api/v1/analysis", json=request)

    assert response.status_code == 422


def test_too_many_samples_returns_400(client: TestClient):
    request = {
        **ANALYSIS_REQUEST,
        "start_time": "2026-11-01T00:00:00Z",
        "stop_time": "2026-12-01T00:00:00Z",
        "step_minutes": 1,
    }
    response = client.post("/api/v1/analysis", json=request)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
