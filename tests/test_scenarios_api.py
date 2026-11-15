from fastapi.testclient import TestClient


def _scenario(label: str, site_id: str, start: str = "2026-11-15T00:00:00Z") -> dict:
    return {
        "label": label,
        "site": {"type": "known", "site_id": site_id},
        "start_time": start,
        "stop_time": "2026-11-16T00:00:00Z",
        "step_minutes": 360,
        "thresholds": {"sun_elevation_deg": 0.0, "earth_elevation_deg": 5.0},
    }


def test_compare_scenarios(client: TestClient):
    response = client.post(
        "/api/v1/scenarios/compare",
        json={
            "scenarios": [
                _scenario("Shackleton", "shackleton-rim"),
                _scenario("Apollo 11", "apollo-11"),
            ]
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["scenarios"]) == 2
    assert all(item["status"] == "ok" for item in payload["scenarios"])
    assert all(item["analysis_id"] for item in payload["scenarios"])
    assert payload["scenarios"][0]["summary"]["total_samples"] == 5
    assert any("does not compute" in caveat for caveat in payload["caveats"])


def test_compare_reports_scenario_errors_without_fake_data(client: TestClient):
    response = client.post(
        "/api/v1/scenarios/compare",
        json={
            "scenarios": [
                _scenario("Valid", "shackleton-rim"),
                _scenario("Invalid", "missing-site"),
            ]
        },
    )

    assert response.status_code == 200, response.text
    outcomes = {item["label"]: item for item in response.json()["scenarios"]}
    assert outcomes["Valid"]["status"] == "ok"
    assert outcomes["Invalid"]["status"] == "error"
    assert outcomes["Invalid"].get("summary") is None
    assert "not found" in outcomes["Invalid"]["error"].lower()


def test_compare_requires_at_least_two_scenarios(client: TestClient):
    response = client.post(
        "/api/v1/scenarios/compare",
        json={"scenarios": [_scenario("Only one", "shackleton-rim")]},
    )

    assert response.status_code == 422


def test_compare_requires_unique_labels(client: TestClient):
    response = client.post(
        "/api/v1/scenarios/compare",
        json={
            "scenarios": [
                _scenario("Same", "shackleton-rim"),
                _scenario("Same", "apollo-11"),
            ]
        },
    )

    assert response.status_code == 422
