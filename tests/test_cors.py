from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _make_client(monkeypatch, cors_origins: str):
    monkeypatch.setenv("CORS_ORIGINS", cors_origins)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    import app.core.config as config
    import app.main as main

    importlib.reload(config)
    importlib.reload(main)
    return TestClient(main.app), config


def test_cors_allows_configured_origin(monkeypatch):
    client, config = _make_client(
        monkeypatch,
        "https://my-app.vercel.app,http://localhost:3000",
    )
    try:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://my-app.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in {200, 204}
        assert response.headers.get("access-control-allow-origin") == "https://my-app.vercel.app"
        assert "https://evil.example" not in (
            response.headers.get("access-control-allow-origin") or ""
        )
        assert config.settings.cors_origins == [
            "https://my-app.vercel.app",
            "http://localhost:3000",
        ]
    finally:
        client.close()
        importlib.reload(config)
        import app.main as main

        importlib.reload(main)


def test_cors_does_not_allow_unconfigured_origin(monkeypatch):
    client, config = _make_client(monkeypatch, "https://my-app.vercel.app")
    try:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://other.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None
    finally:
        client.close()
        importlib.reload(config)
        import app.main as main

        importlib.reload(main)
