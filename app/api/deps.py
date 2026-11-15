from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.core.cache import TTLCache
from app.core.config import settings
from app.integrations.horizons import HorizonsClient
from app.integrations.lroc import LrocWmsClient
from app.integrations.moontrek import MoonTrekClient
from app.services.analysis import AnalysisService
from app.services.analysis_store import AnalysisStore
from app.services.comparison import ComparisonService
from app.services.engine import get_engine
from app.services.engine.ephemeris_provider import (
    HorizonsObserverEphemerisProvider,
    HorizonsVectorEphemerisProvider,
    MockDeterministicEphemerisProvider,
    SpiceEphemerisProvider,
)
from app.services.engine.scientific_adapter import ScientificAdapter
from app.services.ephemeris import EphemerisService
from app.services.sites import SiteService
from app.services.sources import SourceService
from app.services.topography import TopographyService
from app.services.types import EphemerisBundle


@lru_cache
def get_site_service() -> SiteService:
    return SiteService.from_file()


@lru_cache
def get_horizons_client() -> HorizonsClient:
    return HorizonsClient(
        settings.horizons_base_url,
        timeout_seconds=settings.horizons_timeout_seconds,
        max_retries=settings.horizons_max_retries,
        max_concurrent=settings.horizons_max_concurrent,
        user_agent=settings.horizons_user_agent,
    )


@lru_cache
def get_ephemeris_cache() -> TTLCache[tuple[object, ...], EphemerisBundle]:
    return TTLCache(
        ttl_seconds=settings.ephemeris_cache_ttl_seconds,
        max_entries=512,
    )


def get_ephemeris_service(
    horizons: HorizonsClient = Depends(get_horizons_client),
    cache: TTLCache[tuple[object, ...], EphemerisBundle] = Depends(get_ephemeris_cache),
) -> EphemerisService:
    return EphemerisService(horizons, cache, settings)


def get_scientific_engine(
    horizons: HorizonsClient = Depends(get_horizons_client),
) -> object:
    name = settings.scientific_engine
    if name == "scientific-lunaris":
        provider_name = getattr(settings, "scientific_ephemeris_provider", "mock")
        if provider_name == "mock":
            provider = MockDeterministicEphemerisProvider()
        elif provider_name in {"horizons", "horizons-observer"}:
            provider = HorizonsObserverEphemerisProvider(client=horizons)
        elif provider_name == "horizons-vectors":
            provider = HorizonsVectorEphemerisProvider()
        elif provider_name == "spice":
            kernels = getattr(settings, "spice_kernel_paths", None) or []
            if isinstance(kernels, str):
                kernels = [k.strip() for k in kernels.split(",") if k.strip()]
            provider = SpiceEphemerisProvider(kernel_paths=kernels)
        else:
            provider = MockDeterministicEphemerisProvider()
        return ScientificAdapter(ephemeris_provider=provider)
    return get_engine(name)


@lru_cache
def get_analysis_store() -> AnalysisStore:
    return AnalysisStore(
        ttl_seconds=settings.analysis_store_ttl_seconds,
        max_entries=settings.analysis_store_max_entries,
    )


def get_analysis_service(
    site_service: SiteService = Depends(get_site_service),
    ephemeris_service: EphemerisService = Depends(get_ephemeris_service),
    engine: object = Depends(get_scientific_engine),
    store: AnalysisStore = Depends(get_analysis_store),
) -> AnalysisService:
    return AnalysisService(
        site_service=site_service,
        ephemeris_service=ephemeris_service,
        engine=engine,
        store=store,
        settings=settings,
    )


def get_comparison_service(
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> ComparisonService:
    return ComparisonService(analysis_service, settings)


@lru_cache
def get_lroc_client() -> LrocWmsClient:
    return LrocWmsClient(settings.lroc_wms_url)


@lru_cache
def get_moontrek_client() -> MoonTrekClient:
    return MoonTrekClient(settings.moontrek_tiles_url)


def get_topography_service(
    lroc: LrocWmsClient = Depends(get_lroc_client),
    moontrek: MoonTrekClient = Depends(get_moontrek_client),
) -> TopographyService:
    return TopographyService.from_file(
        lroc=lroc,
        moontrek=moontrek,
        settings=settings,
    )


@lru_cache
def get_source_service() -> SourceService:
    return SourceService.from_file()
