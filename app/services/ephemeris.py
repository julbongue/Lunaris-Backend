from __future__ import annotations

import asyncio

from app.core.cache import TTLCache
from app.core.config import Settings
from app.core.exceptions import BadRequestError, UpstreamServiceError
from app.integrations.horizons import (
    EARTH_HORIZONS_ID,
    SUN_HORIZONS_ID,
    EphemerisPoint,
    HorizonsClient,
)
from app.schemas.common import TimeRange
from app.schemas.sites import Site
from app.services.types import CombinedPoint, EphemerisBundle


class EphemerisService:
    def __init__(
        self,
        horizons: HorizonsClient,
        cache: TTLCache[tuple[object, ...], EphemerisBundle],
        settings: Settings,
    ) -> None:
        self._horizons = horizons
        self._cache = cache
        self._settings = settings

    async def get_combined(
        self,
        site: Site,
        time_range: TimeRange,
    ) -> EphemerisBundle:
        self._validate_limits(time_range)
        key = self._cache_key(site, time_range)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sun_points, earth_points = await asyncio.gather(
            self._fetch(SUN_HORIZONS_ID, "Sun", site, time_range),
            self._fetch(EARTH_HORIZONS_ID, "Earth", site, time_range),
        )
        bundle = self._merge(sun_points, earth_points)
        self._cache.set(key, bundle)
        return bundle

    async def _fetch(
        self,
        target: str,
        target_name: str,
        site: Site,
        time_range: TimeRange,
    ) -> list[EphemerisPoint]:
        return await self._horizons.get_site_altaz(
            target=target,
            target_name=target_name,
            latitude_deg=site.latitude_deg,
            longitude_deg=site.longitude_deg,
            elevation_m=site.elevation_m,
            start_time=time_range.start_time,
            stop_time=time_range.stop_time,
            step_minutes=time_range.step_minutes,
        )

    def _validate_limits(self, time_range: TimeRange) -> None:
        span_seconds = (time_range.stop_time - time_range.start_time).total_seconds()
        span_days = span_seconds / 86400.0
        if span_days > self._settings.max_analysis_span_days:
            raise BadRequestError(
                "Requested time range exceeds the configured maximum.",
                details={
                    "max_span_days": self._settings.max_analysis_span_days,
                    "requested_span_days": round(span_days, 3),
                },
            )

        expected_samples = int(span_seconds / 60.0 / time_range.step_minutes) + 1
        if expected_samples > self._settings.max_analysis_samples:
            raise BadRequestError(
                "Requested sampling produces too many samples.",
                details={
                    "max_samples": self._settings.max_analysis_samples,
                    "estimated_samples": expected_samples,
                    "step_minutes": time_range.step_minutes,
                },
            )

    @staticmethod
    def _cache_key(site: Site, time_range: TimeRange) -> tuple[object, ...]:
        return (
            "horizons-altaz-v1",
            round(site.latitude_deg, 6),
            round(site.longitude_deg, 6),
            None if site.elevation_m is None else round(site.elevation_m, 3),
            time_range.start_time.isoformat(),
            time_range.stop_time.isoformat(),
            time_range.step_minutes,
        )

    @staticmethod
    def _merge(
        sun_points: list[EphemerisPoint],
        earth_points: list[EphemerisPoint],
    ) -> EphemerisBundle:
        sun_by_time = {point.timestamp: point for point in sun_points}
        earth_by_time = {point.timestamp: point for point in earth_points}
        common_times = sorted(set(sun_by_time) & set(earth_by_time))

        warnings: list[str] = []
        if not common_times:
            raise UpstreamServiceError(
                "JPL Horizons returned no common Sun/Earth timestamps.",
                details={
                    "sun_samples": len(sun_points),
                    "earth_samples": len(earth_points),
                },
            )
        if len(common_times) != len(sun_points) or len(common_times) != len(earth_points):
            warnings.append(
                "Sun and Earth ephemerides did not share every timestamp; only common "
                "sampled instants were analyzed."
            )

        points = [
            CombinedPoint(
                timestamp=timestamp,
                sun_azimuth_deg=sun_by_time[timestamp].azimuth_deg,
                sun_elevation_deg=sun_by_time[timestamp].elevation_deg,
                earth_azimuth_deg=earth_by_time[timestamp].azimuth_deg,
                earth_elevation_deg=earth_by_time[timestamp].elevation_deg,
            )
            for timestamp in common_times
        ]
        return EphemerisBundle(points=points, warnings=warnings)
