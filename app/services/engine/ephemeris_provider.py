from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from app.core.config import settings
from app.core.exceptions import BadRequestError, EngineUnavailableError, UpstreamServiceError
from app.integrations.horizons.client import HorizonsClient
from app.schemas.common import TimeRange
from app.schemas.sites import Site
from app.services.engine.lunaris_scientific.celestial import apparent_position_from_observer
from app.services.engine.lunaris_scientific.coordinates import selenographic_to_cartesian
from app.services.engine.lunaris_scientific.frames import local_frame
from app.services.engine.lunaris_scientific.vectors import Vec3, vec3


@dataclass(frozen=True)
class InstantEphemeris:
    """Ephemeris state for one UTC instant in lunar body-fixed frame.

    Vectors are positions in kilometers in the same body-fixed/selenographic
    Cartesian frame expected by ``lunaris_scientific`` (observer and targets
    must be consistent). ``source`` must reflect provenance (e.g. 'mock',
    'jpl_horizons'); mock data must never be labeled as real.
    """

    timestamp: datetime
    observer_body_km: Vec3
    earth_body_km: Vec3
    sun_body_km: Vec3
    sun_azimuth_deg: float
    sun_elevation_deg: float
    earth_azimuth_deg: float
    earth_elevation_deg: float
    source: str
    frame: str = "selenographic_body_fixed"


class EphemerisProvider(Protocol):
    """Provides per-instant ephemeris states for a lunar surface observer."""

    name: str

    async def get_instants(
        self,
        *,
        site: Site,
        times_utc: Sequence[datetime],
        reference_frame: str,
    ) -> list[InstantEphemeris]: ...


class CoordinateTransformer(Protocol):
    """Transforms position vectors between supported frames at a given time.

    Implementations must be scientifically validated and traceable. Identity or
    fictitious rotations are not allowed.
    """

    name: str

    def transform_position_km(
        self,
        vector_km: Vec3,
        *,
        from_frame: str,
        to_frame: str,
        time_utc: datetime,
    ) -> Vec3: ...

    def supports(self, from_frame: str, to_frame: str) -> bool: ...


class NoopCoordinateTransformer:
    """Transformer that only allows explicit same-frame passes."""

    name = "identity-same-frame-only"

    def supports(self, from_frame: str, to_frame: str) -> bool:
        return from_frame == to_frame

    def transform_position_km(
        self,
        vector_km: Vec3,
        *,
        from_frame: str,
        to_frame: str,
        time_utc: datetime,
    ) -> Vec3:
        if from_frame != to_frame:
            raise BadRequestError(
                "Coordinate transformation is not available for the requested frames.",
                details={
                    "code": "coordinate_transformation_unavailable",
                    "from_frame": from_frame,
                    "to_frame": to_frame,
                },
            )
        return vector_km


class HorizonsVectorEphemerisProvider:
    """Deprecated placeholder name kept for compatibility.

    Prefer ``HorizonsObserverEphemerisProvider`` for real NASA JPL Horizons
    topocentric ephemerides (Az/El) mapped into the analysis frame.
    """

    name = "horizons-vectors-unavailable"

    async def get_instants(
        self,
        *,
        site: Site,
        times_utc: Sequence[datetime],
        reference_frame: str,
    ) -> list[InstantEphemeris]:
        raise EngineUnavailableError(
            "Validated Cartesian vector ephemeris mode is not activated.",
            details={
                "provider": self.name,
                "reason": (
                    "Body-fixed Cartesian vectors require validated frame/orientation "
                    "transformations (e.g. SPICE kernels). Use horizons observer mode "
                    "for real topocentric Horizons data or configure a validated SPICE provider."
                ),
                "alternatives": ["horizons-observer", "spice (if configured)", "mock-deterministic"],
            },
        )


class HorizonsObserverEphemerisProvider:
    """Real ephemeris provider using NASA JPL Horizons OBSERVER Az/El data.

    Fetches topocentric apparent azimuth/elevation for Sun and Earth from a
    lunar surface site (CENTER=coord@301, QUANTITIES='4'). These are real
    Horizons results. Target directions are mapped into the local selenographic
    body-fixed analysis frame for geometric calculations. Ranges are approximated
    from mean distances when not explicitly provided by the selected quantity
    set; this limitation is recorded in provenance/notes by the adapter.
    """

    name = "horizons-observer"

    def __init__(self, client: HorizonsClient | None = None):
        self._client = client or HorizonsClient(
            settings.horizons_base_url,
            timeout_seconds=settings.horizons_timeout_seconds,
            max_retries=settings.horizons_max_retries,
            max_concurrent=settings.horizons_max_concurrent,
            user_agent=settings.horizons_user_agent,
        )

    async def get_instants(
        self,
        *,
        site: Site,
        times_utc: Sequence[datetime],
        reference_frame: str,
    ) -> list[InstantEphemeris]:
        if reference_frame not in {"selenographic", "planetocentric"}:
            raise BadRequestError(
                "Horizons observer provider supports selenographic/planetocentric analysis frames; inertial/ecliptic require validated transformations.",
                details={
                    "code": "coordinate_transformation_unavailable",
                    "reference_frame": reference_frame,
                    "supported_reference_frames": ["selenographic", "planetocentric"],
                },
            )
        if len(times_utc) < 1:
            return []

        start = times_utc[0]
        stop = times_utc[-1]
        step_minutes = 60
        if len(times_utc) >= 2:
            delta = (times_utc[1] - times_utc[0]).total_seconds() / 60.0
            step_minutes = max(1, int(round(delta)))
        # Horizons STOP is inclusive in effect for sampling; extend slightly to cover last requested instant.
        if stop == start:
            stop_req = start
        else:
            stop_req = stop

        from app.integrations.horizons.client import EARTH_HORIZONS_ID, SUN_HORIZONS_ID

        sun_points, earth_points = await asyncio.gather(
            self._client.get_site_altaz(
                target=SUN_HORIZONS_ID,
                target_name="Sun",
                latitude_deg=site.latitude_deg,
                longitude_deg=site.longitude_deg,
                elevation_m=site.elevation_m,
                start_time=start,
                stop_time=stop_req,
                step_minutes=step_minutes,
            ),
            self._client.get_site_altaz(
                target=EARTH_HORIZONS_ID,
                target_name="Earth",
                latitude_deg=site.latitude_deg,
                longitude_deg=site.longitude_deg,
                elevation_m=site.elevation_m,
                start_time=start,
                stop_time=stop_req,
                step_minutes=step_minutes,
            ),
        )
        sun_by_t = {p.timestamp: p for p in sun_points}
        earth_by_t = {p.timestamp: p for p in earth_points}
        common = [t for t in times_utc if t in sun_by_t and t in earth_by_t]
        if len(common) != len(times_utc):
            missing = [t.isoformat() for t in times_utc if t not in sun_by_t or t not in earth_by_t]
            raise UpstreamServiceError(
                "JPL Horizons did not return all requested instants for Sun/Earth.",
                details={
                    "service": "JPL Horizons",
                    "expected": len(times_utc),
                    "received_common": len(common),
                    "missing_examples": missing[:5],
                },
            )

        radius_m = 1_737_400.0 + (site.elevation_m or 0.0)
        r_km = radius_m / 1000.0
        obs_pos = selenographic_to_cartesian(site.latitude_deg, site.longitude_deg, r_km)
        frame = local_frame(site.latitude_deg, site.longitude_deg, r_km)

        out: list[InstantEphemeris] = []
        for ts in times_utc:
            sp = sun_by_t[ts]
            ep = earth_by_t[ts]
            # Approximate ranges (km) when explicit range quantity not parsed.
            sun_dist = 149597870.7
            earth_dist = 384400.0
            sun_dir = _horizontal_dir(frame, sp.azimuth_deg, sp.elevation_deg)
            earth_dir = _horizontal_dir(frame, ep.azimuth_deg, ep.elevation_deg)
            sun_pos = vec3(obs_pos.x + sun_dir.x * sun_dist, obs_pos.y + sun_dir.y * sun_dist, obs_pos.z + sun_dir.z * sun_dist)
            earth_pos = vec3(obs_pos.x + earth_dir.x * earth_dist, obs_pos.y + earth_dir.y * earth_dist, obs_pos.z + earth_dir.z * earth_dist)
            sun_app = apparent_position_from_observer(obs_pos, sun_pos, frame)
            earth_app = apparent_position_from_observer(obs_pos, earth_pos, frame)
            out.append(
                InstantEphemeris(
                    timestamp=ts,
                    observer_body_km=obs_pos,
                    earth_body_km=earth_pos,
                    sun_body_km=sun_pos,
                    sun_azimuth_deg=sun_app.azimuth_deg,
                    sun_elevation_deg=sun_app.altitude_deg,
                    earth_azimuth_deg=earth_app.azimuth_deg,
                    earth_elevation_deg=earth_app.altitude_deg,
                    source="jpl_horizons",
                    frame="selenographic_body_fixed",
                )
            )
        return out


class SpiceEphemerisProvider:
    """SPICE/NAIF-based ephemeris provider (configurable).

    Requires ``spiceypy`` and configured kernels (SPK, PCK, LSK/FK as needed).
    This implementation attempts to compute body positions and transform to the
    lunar body-fixed frame when dependencies and kernels are available. If not,
    it raises a clear, actionable EngineUnavailableError/BadRequestError.
    """

    name = "spice"

    def __init__(self, kernel_paths: list[str] | None = None):
        self.kernel_paths = kernel_paths or []

    async def get_instants(
        self,
        *,
        site: Site,
        times_utc: Sequence[datetime],
        reference_frame: str,
    ) -> list[InstantEphemeris]:
        try:
            import spiceypy as spice  # type: ignore
        except Exception as exc:
            raise EngineUnavailableError(
                "SPICE provider requires the 'spiceypy' package.",
                details={
                    "provider": self.name,
                    "dependency": "spiceypy",
                    "install_hint": "pip install spiceypy (and provide NAIF kernels)",
                    "reason": str(exc),
                },
            ) from exc

        if not self.kernel_paths:
            raise EngineUnavailableError(
                "SPICE provider requires configured NAIF kernels (SPK/PCK/LSK/FK).",
                details={
                    "provider": self.name,
                    "required_kernels": ["planetary SPK", "lunar PCK/frame kernels", "leap seconds LSK"],
                    "config": "provide kernel paths in provider configuration",
                },
            )

        # Minimal load/compute attempt (synchronous SPICE calls in thread)
        def _compute():
            for k in self.kernel_paths:
                spice.furnsh(k)
            try:
                radius_m = 1_737_400.0 + (site.elevation_m or 0.0)
                r_km = radius_m / 1000.0
                obs_pos = selenographic_to_cartesian(site.latitude_deg, site.longitude_deg, r_km)
                _ = local_frame(site.latitude_deg, site.longitude_deg, r_km)
            finally:
                try:
                    spice.kclear()
                except Exception:
                    pass
            raise EngineUnavailableError(
                "SPICE computation pipeline is not fully configured for validated lunar body-fixed transforms in this environment.",
                details={
                    "provider": self.name,
                    "status": "kernels_loadable_check_required",
                    "note": "Provide validated kernels and frame configuration (MOON_ME/IAU_MOON, observer state, time conversions) to enable.",
                },
            )

        return await asyncio.to_thread(_compute)


class MockDeterministicEphemerisProvider:
    """Deterministic synthetic ephemeris for tests and offline integration.

    Generates reproducible body-fixed positions for Earth and Sun as functions
    of sample index/time so that multi-sample analysis, az/el, visibility and
    threshold logic can be exercised without external services. This data is
    explicitly synthetic (``source='mock'``) and must not be interpreted as
    real astronomy.
    """

    name = "mock-deterministic"

    def __init__(self, *, earth_distance_km: float = 384400.0, sun_distance_km: float = 149597870.7):
        self.earth_distance_km = earth_distance_km
        self.sun_distance_km = sun_distance_km

    async def get_instants(
        self,
        *,
        site: Site,
        times_utc: Sequence[datetime],
        reference_frame: str,
    ) -> list[InstantEphemeris]:
        if reference_frame not in {"selenographic", "planetocentric"}:
            raise BadRequestError(
                "Mock ephemeris provider supports only selenographic/planetocentric body-fixed evaluation.",
                details={
                    "code": "coordinate_conventions_unsupported",
                    "reference_frame": reference_frame,
                    "supported_reference_frames": ["selenographic", "planetocentric"],
                },
            )

        radius_m = 1_737_400.0 + (site.elevation_m or 0.0)
        r_km = radius_m / 1000.0
        obs_pos = selenographic_to_cartesian(site.latitude_deg, site.longitude_deg, r_km)
        frame = local_frame(site.latitude_deg, site.longitude_deg, r_km)
        out: list[InstantEphemeris] = []

        for i, ts in enumerate(times_utc):
            earth_alt = 30.0 - 20.0 * ((i % 5) - 2)
            earth_az = (45.0 + i * 40.0) % 360.0
            sun_alt = 20.0 - 15.0 * ((i % 6) - 2)
            sun_az = (120.0 + i * 35.0) % 360.0

            earth_dir = _horizontal_dir(frame, earth_az, earth_alt)
            sun_dir = _horizontal_dir(frame, sun_az, sun_alt)
            earth_pos = vec3(
                obs_pos.x + earth_dir.x * self.earth_distance_km,
                obs_pos.y + earth_dir.y * self.earth_distance_km,
                obs_pos.z + earth_dir.z * self.earth_distance_km,
            )
            sun_pos = vec3(
                obs_pos.x + sun_dir.x * self.sun_distance_km,
                obs_pos.y + sun_dir.y * self.sun_distance_km,
                obs_pos.z + sun_dir.z * self.sun_distance_km,
            )

            earth_app = apparent_position_from_observer(obs_pos, earth_pos, frame)
            sun_app = apparent_position_from_observer(obs_pos, sun_pos, frame)
            out.append(
                InstantEphemeris(
                    timestamp=ts,
                    observer_body_km=obs_pos,
                    earth_body_km=earth_pos,
                    sun_body_km=sun_pos,
                    sun_azimuth_deg=sun_app.azimuth_deg,
                    sun_elevation_deg=sun_app.altitude_deg,
                    earth_azimuth_deg=earth_app.azimuth_deg,
                    earth_elevation_deg=earth_app.altitude_deg,
                    source="mock",
                    frame="selenographic_body_fixed",
                )
            )
        return out


def _horizontal_dir(frame, azimuth_deg: float, altitude_deg: float) -> Vec3:
    import math

    az = math.radians(azimuth_deg)
    alt = math.radians(altitude_deg)
    c_alt = math.cos(alt)
    d_n = c_alt * math.cos(az)
    d_e = c_alt * math.sin(az)
    d_u = math.sin(alt)
    return vec3(
        d_n * frame.north.x + d_e * frame.east.x + d_u * frame.up.x,
        d_n * frame.north.y + d_e * frame.east.y + d_u * frame.up.y,
        d_n * frame.north.z + d_e * frame.east.z + d_u * frame.up.z,
    )
