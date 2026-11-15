from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["project"] == "LUNARIS"
    assert payload["engine"] == "geometric"


def test_root(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to LUNARIS API"
