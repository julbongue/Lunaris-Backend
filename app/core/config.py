from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    scientific_engine: str = "geometric"
    scientific_ephemeris_provider: str = "mock"  # mock | horizons/horizons-observer | spice | horizons-vectors
    spice_kernel_paths: str | list[str] = Field(default_factory=list)

    max_analysis_span_days: int = 35
    max_analysis_samples: int = 5000
    max_comparison_scenarios: int = 6
    ephemeris_cache_ttl_seconds: int = 300
    analysis_store_ttl_seconds: int = 1800
    analysis_store_max_entries: int = 256

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


settings = Settings()
