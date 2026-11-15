from fastapi.testclient import TestClient


def test_list_topography_layers(client: TestClient):
    response = client.get("/api/v1/topography/layers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 6
    ids = {layer["id"] for layer in payload["layers"]}
    assert {"lroc-wac-global", "moontrek-wac-global"} <= ids
    assert any("not queryable" in caveat for caveat in payload["caveats"])


def test_topography_context_for_known_site(client: TestClient):
    response = client.post(
        "/api/v1/topography/context",
        json={
            "site": {"type": "known", "site_id": "shackleton-rim"},
            "layer_id": "lroc-wac-global",
            "size_deg": 0.5,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["elevation_available"] is False
    assert payload["elevation_m"] is None
    assert payload["bbox"]["min_latitude_deg"] == -90.0
    assert payload["bbox"]["max_latitude_deg"] == -89.65
    assert "GetMap" in payload["map_url"]
    assert "luna_wac_global" in payload["map_url"]
    assert any("does not infer" in note for note in payload["notes"])


def test_topography_context_for_custom_site_with_elevation(client: TestClient):
    response = client.post(
        "/api/v1/topography/context",
        json={
            "site": {
                "type": "coordinates",
                "latitude_deg": -88.0,
                "longitude_deg": 10.0,
                "elevation_m": 1234.0,
            },
            "layer_id": "moontrek-wac-global",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["elevation_available"] is True
    assert payload["elevation_m"] == 1234.0
    assert payload["elevation_source"] == "user-provided"
    assert "tile_url_template" in payload
    assert "WMTSCapabilities.xml" in payload["capabilities_url"]


def test_topography_unknown_layer_returns_404(client: TestClient):
    response = client.post(
        "/api/v1/topography/context",
        json={
            "site": {"type": "known", "site_id": "shackleton-rim"},
            "layer_id": "not-a-layer",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_topography_invalid_size_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/topography/context",
        json={
            "site": {"type": "known", "site_id": "shackleton-rim"},
            "size_deg": 100.0,
        },
    )

    assert response.status_code == 422
