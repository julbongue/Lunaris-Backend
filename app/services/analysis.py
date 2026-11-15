from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    EphemerisSample,
    SourceReference,
)
from app.schemas.common import TimeRange
from app.schemas.sites import Site
from app.services.analysis_store import AnalysisStore
from app.services.engine.base import EngineInput
from app.services.ephemeris import EphemerisService
from app.services.sites import SiteService


class AnalysisService:
    def __init__(
        self,
        site_service: SiteService,
        ephemeris_service: EphemerisService,
        engine: object,
        store: AnalysisStore,
        settings: Settings,
    ) -> None:
        self._site_service = site_service
        self._ephemeris_service = ephemeris_service
        self._engine = engine
        self._store = store
        self._settings = settings

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        site = self._site_service.resolve(request.site)

        # Scientific adapter path: per-instant definitive evaluation + aggregation
        if hasattr(self._engine, "analyze_request"):
            out = await self._engine.analyze_request(request, site)
            samples = None
            if request.include_samples:
                samples = [
                    EphemerisSample(
                        timestamp=p.timestamp,
                        sun_azimuth_deg=round(p.sun_azimuth_deg, 6),
                        sun_elevation_deg=round(p.sun_elevation_deg, 6),
                        sun_above_threshold=(p.sun_elevation_deg >= request.thresholds.sun_elevation_deg),
                        earth_azimuth_deg=round(p.earth_azimuth_deg, 6),
                        earth_elevation_deg=round(p.earth_elevation_deg, 6),
                        earth_above_threshold=(p.earth_elevation_deg >= request.thresholds.earth_elevation_deg),
                    )
                    for p in out.samples_points
                ]

            # Representative instant fields: use last instant if available (not invented)
            rep_earth = rep_sun = rep_sun_c = rep_earth_c = rep_illum = rep_cond = rep_hor = None
            if out.instants:
                rep = out.instants[-1].result
                rep_earth = rep.earth
                rep_sun = rep.sun
                rep_sun_c = rep.sun_coordinates
                rep_earth_c = rep.earth_coordinates
                rep_illum = rep.illumination
                rep_cond = rep.conditions
                rep_hor = rep.horizon

            caveats = self._caveats(site, [], out.model.limitations)
            caveats.extend(out.caveats)
            result = AnalysisResult(
                analysis_id=str(uuid4()),
                created_at=datetime.now(UTC),
                site=site,
                time_range=TimeRange(
                    start_time=request.start_time,
                    stop_time=request.stop_time,
                    step_minutes=request.step_minutes,
                ),
                thresholds=request.thresholds,
                summary=out.summary,
                solar_windows=out.solar_windows,
                communication_windows=out.communication_windows,
                samples=samples,
                model=out.model,
                sources=self._sources(site, scientific=True, provider=getattr(self._engine, "_provider", None)),
                caveats=caveats,
                earth=rep_earth,
                sun=rep_sun,
                sun_coordinates=rep_sun_c,
                earth_coordinates=rep_earth_c,
                illumination=rep_illum,
                conditions=rep_cond,
                horizon=rep_hor,
                quality=out.quality,
            )
            self._store.put(result)
            return result

        # Legacy path (geometric baseline)
        bundle = await self._ephemeris_service.get_combined(site, request)
        engine_output = self._engine.analyze(
            EngineInput(
                points=bundle.points,
                thresholds=request.thresholds,
                range_start=request.start_time,
                range_end=request.stop_time,
                step_minutes=request.step_minutes,
            )
        )

        samples = None
        if request.include_samples:
            samples = [
                EphemerisSample(
                    timestamp=point.timestamp,
                    sun_azimuth_deg=round(point.sun_azimuth_deg, 6),
                    sun_elevation_deg=round(point.sun_elevation_deg, 6),
                    sun_above_threshold=(
                        point.sun_elevation_deg >= request.thresholds.sun_elevation_deg
                    ),
                    earth_azimuth_deg=round(point.earth_azimuth_deg, 6),
                    earth_elevation_deg=round(point.earth_elevation_deg, 6),
                    earth_above_threshold=(
                        point.earth_elevation_deg >= request.thresholds.earth_elevation_deg
                    ),
                )
                for point in bundle.points
            ]

        result = AnalysisResult(
            analysis_id=str(uuid4()),
            created_at=datetime.now(UTC),
            site=site,
            time_range=TimeRange(
                start_time=request.start_time,
                stop_time=request.stop_time,
                step_minutes=request.step_minutes,
            ),
            thresholds=request.thresholds,
            summary=engine_output.summary,
            solar_windows=engine_output.solar_windows,
            communication_windows=engine_output.communication_windows,
            samples=samples,
            model=engine_output.model,
            sources=self._sources(site, scientific=False),
            caveats=self._caveats(
                site,
                bundle.warnings,
                engine_output.model.limitations,
            ),
        )
        self._store.put(result)
        return result

    def get(self, analysis_id: str) -> AnalysisResult:
        result = self._store.get(analysis_id)
        if result is None:
            raise NotFoundError(
                f"Analysis '{analysis_id}' was not found or has expired.",
                details={"analysis_id": analysis_id},
            )
        return result

    def _sources(self, site: Site, scientific: bool = False, provider=None) -> list[SourceReference]:
        sources = []
        if scientific:
            pname = getattr(provider, "name", "scientific-ephemeris-provider")
            if pname == "mock-deterministic" or getattr(provider, "name", "") == "mock-deterministic":
                sources.append(
                    SourceReference(
                        name="Mock deterministic ephemeris (synthetic)",
                        url="https://example.invalid/mock-ephemeris",
                        description="Synthetic deterministic vectors for testing; not real astronomical data.",
                    )
                )
            else:
                sources.append(
                    SourceReference(
                        name="JPL Horizons",
                        url=self._settings.horizons_base_url,
                        description="Ephemeris source configured for scientific analysis (subject to provider validation).",
                    )
                )
        else:
            sources.append(
                SourceReference(
                    name="JPL Horizons",
                    url=self._settings.horizons_base_url,
                    description=(
                        "Topocentric Sun and Earth altitude/azimuth samples for a lunar "
                        "surface observer."
                    ),
                )
            )
        if site.source_url is not None:
            sources.append(
                SourceReference(
                    name=f"Site coordinate source: {site.name}",
                    url=str(site.source_url),
                    description="Published source used for the curated site coordinates.",
                )
            )
        return sources

    @staticmethod
    def _caveats(
        site: Site,
        warnings: list[str],
        model_limitations: list[str],
    ) -> list[str]:
        caveats = [*model_limitations, *warnings]
        if site.elevation_m is None:
            caveats.append(
                "No site elevation was provided; JPL Horizons used 0 km altitude for "
                "the topocentric calculation."
            )
        if site.is_custom:
            caveats.append(
                "Custom coordinates are normalized for this request and are not persisted."
            )
        return caveats
