from __future__ import annotations

import importlib


def test_cors_origins_parses_comma_separated_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app, http://localhost:3000")
    import app.core.config as config

    importlib.reload(config)
    try:
        assert config.settings.cors_origins == [
            "https://a.vercel.app",
            "http://localhost:3000",
        ]
    finally:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        importlib.reload(config)


def test_cors_origins_parses_json_array(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.vercel.app","http://localhost:5173"]')
    import app.core.config as config

    importlib.reload(config)
    try:
        assert config.settings.cors_origins == [
            "https://a.vercel.app",
            "http://localhost:5173",
        ]
    finally:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        importlib.reload(config)


def test_host_and_port_from_env(monkeypatch):
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9001")
    import app.core.config as config

    importlib.reload(config)
    try:
        assert config.settings.host == "127.0.0.1"
        assert config.settings.port == 9001
    finally:
        monkeypatch.delenv("HOST", raising=False)
        monkeypatch.delenv("PORT", raising=False)
        importlib.reload(config)
