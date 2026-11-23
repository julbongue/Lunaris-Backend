from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _env_file() -> str | None:
    """Load .env only when it is a regular file.

    The repository may contain a directory named .env (for example, a
    virtual environment created with that name).  pydantic-settings should not
    try to parse it as a configuration file.
    """

    path = Path(".env")
    return str(path) if path.is_file() else None


class Settings(BaseSettings):
    app_name: str = "LUNARIS API"
    app_version: str = "1.0.0"
    app_description: str = (
        "LUNARIS - Lunar Landing Site Navigator. API for comparing lunar sites and landing dates."
    )
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    # Comma-separated list or JSON array. Example:
    # CORS_ORIGINS=https://app.vercel.app,http://localhost:3000
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    scientific_engine: str = "geometric"
    scientific_ephemeris_provider: str = (
        "mock"  # mock | horizons/horizons-observer | spice | horizons-vectors
    )
    spice_kernel_paths: Annotated[str | list[str], NoDecode] = Field(default_factory=list)

    max_analysis_span_days: int = 35
    max_analysis_samples: int = 5000
    max_comparison_scenarios: int = 6
    ephemeris_cache_ttl_seconds: int = 300
    analysis_store_ttl_seconds: int = 1800
    analysis_store_max_entries: int = 256

    database_url: str | None = None
    lunar_sites_table: str = "lunar_sites"
    database_pool_pre_ping: bool = True
    # Basic request protection (reverse proxy/tunnel should still enforce limits).
    max_request_body_bytes: int = 1_000_000
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    trust_proxy_headers: bool = False

    horizons_base_url: str = "https://ssd.jpl.nasa.gov/api/horizons.api"
    horizons_timeout_seconds: float = 45.0
    horizons_max_retries: int = 1
    horizons_max_concurrent: int = 4
    horizons_user_agent: str = "LUNARIS/1.0 (NASA Space Apps 2026)"

    lroc_wms_url: str = "https://wms.im-ldi.com/lroc/wms"
    moontrek_tiles_url: str = "https://trek.nasa.gov/tiles/Moon"
    moontrek_catalog_url: str = (
        "https://trek.nasa.gov/moon/TrekServices/ws/index/eq/listVisibleLayers"
    )
    topography_default_size_deg: float = 0.5
    topography_map_size_px: int = 1024

    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "CORS_ORIGINS must be a JSON array or a comma-separated list of origins."
                    ) from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be a list.")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("spice_kernel_paths", mode="before")
    @classmethod
    def parse_spice_kernel_paths(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = [item.strip() for item in raw.split(",") if item.strip()]
                return parsed if isinstance(parsed, list) else [str(parsed)]
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value


settings = Settings()
