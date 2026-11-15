from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.deps import get_site_service
from app.core.config import settings
from app.schemas.common import ApiModel
from app.services.sites import SiteService

router = APIRouter()


class EngineCapability(ApiModel):
    name: str
    available: bool
    mode: str
    notes: list[str] = []


class HealthResponse(ApiModel):
    status: str
    project: str
    version: str
    timestamp: datetime
    engine: str


class CapabilitiesResponse(ApiModel):
    status: str
    configured_engine: str
    configured_ephemeris_provider: str
    engines: list[EngineCapability]
    features: dict[str, bool | str | list[str]]


@router.get("/health", tags=["Health"], response_model=HealthResponse)
def health_check(service: SiteService = Depends(get_site_service)) -> HealthResponse:
    # Touching the site service verifies that the local dataset is loadable.
    service.list_sites()
    return HealthResponse(
        status="healthy",
        project="LUNARIS",
        version=settings.app_version,
        timestamp=datetime.now(UTC),
        engine=settings.scientific_engine,
    )


@router.get("/capabilities", tags=["Health"], response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    provider = getattr(settings, "scientific_ephemeris_provider", "mock")
    engines = [
        EngineCapability(
            name="geometric",
            available=True,
            mode="legacy",
            notes=["Horizons Az/El sampled geometry baseline (legacy-compatible)."],
        ),
        EngineCapability(
            name="scientific-lunaris",
            available=True,
            mode="per-instant-geometric",
            notes=[
                "Per-instant scientific adapter with service-level temporal aggregation.",
                "Providers: mock-deterministic, horizons-observer (real JPL Horizons Az/El), spice (requires spiceypy+kernels), horizons-vectors (unavailable).",
            ],
        ),
    ]
    return CapabilitiesResponse(
        status="healthy",
        configured_engine=settings.scientific_engine,
        configured_ephemeris_provider=provider,
        engines=engines,
        features={
            "analysis_create_get": True,
            "scenario_comparison": True,
            "temporal_aggregation": True,
            "per_instant_scientific_results": "scientific-lunaris with mock/validated provider",
            "geometric_visibility": True,
            "geometric_illumination_angles": "available with scientific-lunaris when vectors provided",
            "terrain_dem_obstruction": "not_available (no validated DEM integration)",
            "real_vector_ephemeris": "partial (horizons-observer real Az/El available; validated body-fixed Cartesian/SPICE transforms depend on configuration/kernels)",
        },
    )
