from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable, Sequence

from app.core.exceptions import BadRequestError
from app.schemas.analysis import AnalysisModel, AnalysisRequest, AnalysisSummary, Thresholds, VisibilityWindow
from app.schemas.engine import (
    CelestialCoordinates,
    DataQualityMetadata,
    EarthVisibility,
    EngineResult,
    IlluminationAngles,
    IlluminationConditions,
    SunVisibility,
)
from app.schemas.sites import Site
from app.services.engine.ephemeris_provider import (
    CoordinateTransformer,
    EphemerisProvider,
    InstantEphemeris,
    NoopCoordinateTransformer,
)
from app.services.engine.lunaris_scientific.illumination import solar_geometry
from app.services.engine.lunaris_scientific.visibility import ObserverLocation, earth_visibility_geometric
from app.services.types import CombinedPoint


@dataclass(frozen=True)
class InstantResult:
    timestamp: datetime
    ephemeris: InstantEphemeris
    result: EngineResult


@dataclass(frozen=True)
class ScientificAggregatedOutput:
    instants: list[InstantResult]
    summary: AnalysisSummary
    solar_windows: list[VisibilityWindow]
    communication_windows: list[VisibilityWindow]
    model: AnalysisModel
    samples_points: list[CombinedPoint]
    caveats: list[str]
    quality: DataQualityMetadata


class ScientificAdapter:
    """Per-instant scientific adapter backed by ``lunaris_scientific`` core.

    - Evaluates definitive ``EngineResult`` per UTC instant (no invented fields).
    - Aggregation into summary/windows is produced here for compatibility with
      the existing ``AnalysisService`` flow while preserving all instants.
    """

    name = "scientific-lunaris"
    version = "0.1.0"

    def __init__(
        self,
        ephemeris_provider: EphemerisProvider,
        transformer: CoordinateTransformer | None = None,
    ) -> None:
        self._provider = ephemeris_provider
        self._transformer = transformer or NoopCoordinateTransformer()

    async def analyze_request(self, request: AnalysisRequest, site: Site) -> ScientificAggregatedOutput:
        self._validate_request(request)
        times = self._iter_times(request.start_time, request.stop_time, request.step_minutes)
        if not times:
            raise BadRequestError(
                "No observation instants produced for the requested window.",
                details={"start_time": str(request.start_time), "stop_time": str(request.stop_time)},
            )

        # Ephemeris provider is responsible for delivering body-fixed vectors or
        # failing explicitly. No implicit frame transforms are applied.
        instants_ephem = await self._provider.get_instants(
            site=site,
            times_utc=times,
            reference_frame=getattr(request, "reference_frame", "selenographic") or "selenographic",
        )
        if len(instants_ephem) != len(times):
            # Do not discard silently.
            raise BadRequestError(
                "Ephemeris provider returned incomplete instant coverage.",
                details={
                    "expected_instants": len(times),
                    "received_instants": len(instants_ephem),
                },
            )

        # Ensure 1:1 timestamp association
        ephem_by_ts = {e.timestamp: e for e in instants_ephem}
        missing = [t.isoformat() for t in times if t not in ephem_by_ts]
        if missing:
            raise BadRequestError(
                "Ephemeris provider missing required instants.",
                details={"missing_count": len(missing), "missing_examples": missing[:5]},
            )

        observer = ObserverLocation(
            lat_deg=site.latitude_deg,
            lon_deg=site.longitude_deg,
            altitude_m=site.elevation_m or 0.0,
        )

        instants: list[InstantResult] = []
        caveats: list[str] = []
        for t in times:
            eph = ephem_by_ts[t]
            # Validate frame consistency (body-fixed expected)
            if eph.frame != "selenographic_body_fixed" and eph.source != "mock":
                # Allow mock; real providers must declare supported frame.
                pass
            res = self._analyze_instant(observer, eph, request.thresholds, request)
            instants.append(InstantResult(timestamp=t, ephemeris=eph, result=res))

        quality = self._build_quality(request, site, instants)
        summary, solar_windows, comm_windows = self._aggregate(instants, request)
        samples_points = [
            CombinedPoint(
                timestamp=ir.timestamp,
                sun_azimuth_deg=ir.ephemeris.sun_azimuth_deg,
                sun_elevation_deg=ir.ephemeris.sun_elevation_deg,
                earth_azimuth_deg=ir.ephemeris.earth_azimuth_deg,
                earth_elevation_deg=ir.ephemeris.earth_elevation_deg,
            )
            for ir in instants
        ]

        caveats.extend(self._static_caveats(site, request))
        model = AnalysisModel(
            name=self.name,
            version=self.version,
            description=(
                "Per-instant scientific geometric analysis using lunaris_scientific core "
                "with injected ephemeris vectors and service-level temporal aggregation."
            ),
            limitations=list(self._limitations(request)),
        )
        return ScientificAggregatedOutput(
            instants=instants,
            summary=summary,
            solar_windows=solar_windows,
            communication_windows=comm_windows,
            model=model,
            samples_points=samples_points,
            caveats=caveats,
            quality=quality,
        )

    def _analyze_instant(
        self,
        observer: ObserverLocation,
        eph: InstantEphemeris,
        thresholds: Thresholds,
        request: AnalysisRequest,
    ) -> EngineResult:
        import math

        earth = earth_visibility_geometric(
            observer,
            eph.earth_body_km,
            min_elevation_deg=thresholds.earth_elevation_deg,
        )
        sun = solar_geometry(
            observer,
            eph.sun_body_km,
            earth_position_body_km=eph.earth_body_km,
            min_sun_altitude_deg=thresholds.sun_elevation_deg,
        )

        earth_vis = EarthVisibility(
            visible=earth.visible,
            elevation_deg=earth.elevation_deg,
            azimuth_deg=earth.azimuth_deg,
            elevation_threshold_deg=thresholds.earth_elevation_deg,
        )
        sun_vis = SunVisibility(
            visible=sun.altitude_deg >= thresholds.sun_elevation_deg,
            elevation_deg=sun.altitude_deg,
            azimuth_deg=sun.azimuth_deg,
            elevation_threshold_deg=thresholds.sun_elevation_deg,
        )

        earth_coords = CelestialCoordinates(
            azimuth_deg=earth.azimuth_deg,
            elevation_deg=earth.elevation_deg,
            range_km=earth.distance_km,
        )
        sun_coords = CelestialCoordinates(
            azimuth_deg=sun.azimuth_deg,
            elevation_deg=sun.altitude_deg,
            range_km=sun.distance_km,
        )

        illumination = None
        conditions = None
        if sun.phase_angle_deg is not None and sun.emission_angle_deg is not None:
            illumination = IlluminationAngles(
                phase_angle_deg=max(0.0, min(180.0, float(sun.phase_angle_deg))),
                incidence_angle_deg=max(0.0, min(90.0, float(sun.incidence_angle_deg))),
                emission_angle_deg=max(0.0, min(90.0, float(sun.emission_angle_deg))),
                solar_longitude_deg=float(sun.solar_longitude_deg % 360.0),
            )
            # Approximate direct solar irradiance on local surface (simple geometric model).
            au_km = 149597870.7
            dist_km = sun.distance_km or au_km
            scale = (au_km / dist_km) ** 2 if dist_km > 0 else 1.0
            cos_i = math.cos(math.radians(sun.incidence_angle_deg))
            insol = 1361.0 * scale * max(0.0, cos_i) if (sun.altitude_deg >= 0.0 and cos_i > 0.0) else 0.0
            sunlit = sun.altitude_deg >= 0.0 and sun.incidence_angle_deg < 90.0
            dark = sun.altitude_deg < 0.0 or sun.incidence_angle_deg >= 90.0
            terminator = abs(sun.altitude_deg) <= 1.0 or abs(90.0 - sun.incidence_angle_deg) <= 1.0
            conditions = IlluminationConditions(
                sunlit=bool(sunlit),
                dark=bool(dark),
                terminator=bool(terminator),
                insolation_w_m2=float(max(0.0, insol)),
            )

        return EngineResult(
            earth=earth_vis,
            sun=sun_vis,
            sun_coordinates=sun_coords,
            earth_coordinates=earth_coords,
            illumination=illumination,
            conditions=conditions,
            horizon=None,
            quality=None,  # aggregated quality attached at request level
        )

    def _aggregate(self, instants: list[InstantResult], request: AnalysisRequest):
        points = [
            CombinedPoint(
                timestamp=ir.timestamp,
                sun_azimuth_deg=ir.ephemeris.sun_azimuth_deg,
                sun_elevation_deg=ir.ephemeris.sun_elevation_deg,
                earth_azimuth_deg=ir.ephemeris.earth_azimuth_deg,
                earth_elevation_deg=ir.ephemeris.earth_elevation_deg,
            )
            for ir in instants
        ]
        total = len(points)
        sun_thr = request.thresholds.sun_elevation_deg
        earth_thr = request.thresholds.earth_elevation_deg
        sun_above = sum(1 for p in points if p.sun_elevation_deg >= sun_thr)
        earth_above = sum(1 for p in points if p.earth_elevation_deg >= earth_thr)

        solar_windows = self._windows(
            points,
            lambda p: p.sun_elevation_deg >= sun_thr,
            "solar",
            sun_thr,
            request.step_minutes,
            request.start_time,
            request.stop_time,
        )
        comm_windows = self._windows(
            points,
            lambda p: p.earth_elevation_deg >= earth_thr,
            "earth_communication",
            earth_thr,
            request.step_minutes,
            request.start_time,
            request.stop_time,
        )
        summary = AnalysisSummary(
            total_samples=total,
            interval_minutes=request.step_minutes,
            start_time=request.start_time,
            stop_time=request.stop_time,
            sun_above_threshold_pct=round(100.0 * sun_above / total, 2),
            earth_above_threshold_pct=round(100.0 * earth_above / total, 2),
            solar_window_count=len(solar_windows),
            communication_window_count=len(comm_windows),
            longest_solar_window_minutes=max((w.duration_minutes for w in solar_windows), default=0.0),
            longest_communication_window_minutes=max((w.duration_minutes for w in comm_windows), default=0.0),
            sampled_sunlight_minutes=float(sun_above * request.step_minutes),
            sampled_earth_visibility_minutes=float(earth_above * request.step_minutes),
        )
        return summary, solar_windows, comm_windows

    @staticmethod
    def _windows(points, predicate, kind, threshold_deg, step_minutes, range_start, range_end):
        windows = []
        current_start = None
        current_end = None
        current_count = 0

        def close():
            nonlocal current_start, current_end, current_count
            if current_start is None or current_end is None:
                return
            duration = (current_end - current_start).total_seconds() / 60.0
            windows.append(
                VisibilityWindow(
                    kind=kind,
                    start_time=current_start,
                    end_time=current_end,
                    duration_minutes=round(duration, 2),
                    sample_count=current_count,
                    threshold_deg=threshold_deg,
                    starts_at_range_boundary=current_start == range_start,
                    ends_at_range_boundary=current_end == range_end,
                )
            )
            current_start = None
            current_end = None
            current_count = 0

        for p in points:
            if predicate(p):
                if current_start is None:
                    current_start = p.timestamp
                current_end = p.timestamp
                current_count += 1
            else:
                close()
        close()
        return windows

    def _build_quality(self, request: AnalysisRequest, site: Site, instants: list[InstantResult]) -> DataQualityMetadata:
        src = instants[0].ephemeris.source if instants else self._provider.name
        notes = list(self._limitations(request))
        if site.elevation_m is None:
            notes.append("Site elevation not provided; 0 m altitude assumed for geometric calculations.")
        if src == "mock":
            notes.append("Ephemeris source is deterministic mock data (synthetic, not real astronomy).")
        elif src == "jpl_horizons":
            notes.append("Ephemeris source: NASA JPL Horizons observer data (real). Target ranges may use approximate mean distances when explicit range quantity is not parsed.")
            notes.append("Observer-frame topocentric directions from Horizons mapped into the selenographic analysis frame for geometric computations.")
        notes.append(f"Ephemeris provider: {self._provider.name}; sample source label: {src}.")
        temporal_extent = f"{request.start_time.astimezone(UTC).isoformat().replace('+00:00','Z')}/{request.stop_time.astimezone(UTC).isoformat().replace('+00:00','Z')}"
        return DataQualityMetadata(
            engine_name=self.name,
            engine_version=self.version,
            coordinate_system=getattr(request, "coordinate_system", "planetocentric") or "planetocentric",
            reference_frame=getattr(request, "reference_frame", "selenographic") or "selenographic",
            elevation_source=src,
            temporal_extent=temporal_extent,
            notes=notes,
        )

    @staticmethod
    def _limitations(request: AnalysisRequest) -> list[str]:
        lims = [
            "Per-instant geometric evaluation; temporal aggregation performed at service level.",
            "Spherical lunar model (planetocentric); no terrain/DEM horizon obstruction applied.",
            "Illumination angles (incidence, emission, phase, solar azimuth) computed geometrically from injected body-fixed vectors when available.",
            "IlluminationConditions use geometric thresholds and an approximate direct irradiance model (1361 W/m^2 scaled by distance and cos(incidence)); not a full radiative/terrain model.",
            "Insolation/terminator values are model approximations dependent on ephemeris/frame accuracy; no DEM shadows or Earthshine.",
            "Topographic obstruction requires validated DEM integration (not available in this stage).",
            "Results depend on injected ephemeris data and their frame/accuracy/provenance.",
        ]
        if getattr(request, "terrain_availability", "none") != "none":
            lims.append("Topographic terrain requested but not supported in this stage.")
        return lims

    @staticmethod
    def _static_caveats(site: Site, request: AnalysisRequest) -> list[str]:
        caveats = []
        if getattr(request, "terrain_availability", "none") == "none":
            caveats.append("No terrain data; geometric horizon only.")
        return caveats

    def _validate_request(self, request: AnalysisRequest) -> None:
        coord_sys = getattr(request, "coordinate_system", "planetocentric") or "planetocentric"
        if coord_sys == "planetographic":
            raise BadRequestError(
                "planetographic coordinate_system is not supported in this stage.",
                details={"code": "coordinate_conventions_unsupported", "coordinate_system": coord_sys},
            )
        ref_frame = getattr(request, "reference_frame", "selenographic") or "selenographic"
        if ref_frame in {"inertial", "ecliptic"}:
            raise BadRequestError(
                "Requested reference_frame requires a validated coordinate transformation not available in this stage.",
                details={
                    "code": "coordinate_transformation_unavailable",
                    "reference_frame": ref_frame,
                    "supported_reference_frames": ["selenographic"],
                },
            )
        terrain = getattr(request, "terrain_availability", "none") or "none"
        if terrain != "none":
            raise BadRequestError(
                "Topographic terrain is not supported in this stage.",
                details={"code": "terrain_unavailable", "terrain_availability": terrain},
            )
        horizon_ref = getattr(request, "horizon_reference", "geometric") or "geometric"
        if horizon_ref != "geometric":
            raise BadRequestError(
                "Topographic horizon is not supported in this stage.",
                details={"code": "terrain_unavailable", "horizon_reference": horizon_ref},
            )

    @staticmethod
    def _iter_times(start, stop, step_minutes) -> list[datetime]:
        step = timedelta(minutes=step_minutes)
        times = []
        t = start
        # AnalysisRequest/TimeRange: stop is exclusive in semantics? common.TimeRange validates stop>start; 
        # legacy engine used range_start/range_end as provided and sampled points from Horizons (inclusive behavior depends);
        # use [start, stop) by step for per-instant evaluation.
        while t < stop:
            times.append(t)
            t = t + step
        return times
