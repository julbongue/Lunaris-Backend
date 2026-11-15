from fastapi.testclient import TestClient


def test_list_sites(client: TestClient):
    response = client.get("/api/v1/sites")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 8
    ids = {site["id"] for site in payload["sites"]}
    assert "shackleton-rim" in ids
    assert "apollo-11" in ids


def test_list_south_polar_sites(client: TestClient):
    response = client.get("/api/v1/sites", params={"south_polar_only": True})

    assert response.status_code == 200
    sites = response.json()["sites"]
    assert sites
    assert all(site["is_south_polar"] for site in sites)
    assert {site["id"] for site in sites} >= {"shackleton-rim", "cabeus-crater"}


def test_get_site_derives_longitude_convention(client: TestClient):
    response = client.get("/api/v1/sites/cabeus-crater")

    assert response.status_code == 200
    payload = response.json()
    assert payload["longitude_deg"] == -42.13
    assert payload["longitude_east_deg"] == 317.87
    assert payload["is_south_polar"] is True


def test_get_unknown_site_returns_404(client: TestClient):
    response = client.get("/api/v1/sites/not-a-real-site")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_resolve_custom_coordinates(client: TestClient):
    response = client.post(
        "/api/v1/sites/resolve",
        json={
            "name": "My polar site",
            "latitude_deg": -88.5,
            "longitude_deg": -10.25,
            "elevation_m": 1200.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is False
    assert payload["site"]["is_custom"] is True
    assert payload["site"]["longitude_east_deg"] == 349.75
    assert payload["site"]["elevation_m"] == 1200.0


def test_resolve_invalid_latitude_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/sites/resolve",
        json={"latitude_deg": -100.0, "longitude_deg": 0.0},
    )

    assert response.status_code == 422
