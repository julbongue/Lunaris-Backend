from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_app_startup_and_basic_health():
    app = create_app()
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert root.json()["docs"] == "/docs"

        health = client.get("/api/v1/health")
        assert health.status_code == 200
        payload = health.json()
        assert payload["status"] == "healthy"
        assert payload["project"] == "LUNARIS"

        healthz = client.get("/healthz")
        assert healthz.status_code == 200
        assert healthz.json()["status"] == "ok"
