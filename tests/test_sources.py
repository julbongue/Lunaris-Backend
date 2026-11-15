from fastapi.testclient import TestClient


def test_list_sources(client: TestClient):
    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    payload = response.json()
    by_id = {source["id"]: source for source in payload["sources"]}
    assert by_id["jpl-horizons"]["status"] == "integrated"
    assert by_id["lroc-quickmap"]["status"] == "integrated_map_layers"
    assert by_id["nasa-moon-trek"]["status"] == "integrated_map_layers"
    assert by_id["csa-moon-exploration"]["status"] == "not_integrated"
    assert by_id["naif-spice"]["status"] == "planned"
