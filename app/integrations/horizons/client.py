from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from app.core.exceptions import UpstreamServiceError, UpstreamTimeoutError
from app.integrations.horizons.parser import (
    EphemerisPoint,
    HorizonsParseError,
    parse_altaz_table,
)

logger = logging.getLogger(__name__)

SUN_HORIZONS_ID = "10"
EARTH_HORIZONS_ID = "399"
MOON_HORIZONS_ID = "301"


class HorizonsClient:
    """Thin async client for the public JPL Horizons API.

    Only observer tables with Az/El are requested. The client does not cache;
    caching is handled by EphemerisService.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 45.0,
        max_retries: int = 1,
        max_concurrent: int = 4,
        user_agent: str = "LUNARIS/1.0",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.user_agent = user_agent
        self._transport = transport
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent))

    def build_params(
        self,
        *,
        target: str,
        latitude_deg: float,
        longitude_deg: float,
        elevation_m: float | None,
        start_time: datetime,
        stop_time: datetime,
        step_minutes: int,
    ) -> dict[str, str]:
        altitude_km = (elevation_m if elevation_m is not None else 0.0) / 1000.0
        longitude_east_deg = longitude_deg % 360.0
        return {
            "format": "text",
            "COMMAND": f"'{target}'",
            "OBJ_DATA": "'NO'",
            "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'OBSERVER'",
            "CENTER": f"'coord@{MOON_HORIZONS_ID}'",
            "COORD_TYPE": "'GEODETIC'",
            "SITE_COORD": (f"'{longitude_east_deg:.8f},{latitude_deg:.8f},{altitude_km:.8f}'"),
            "START_TIME": f"'{start_time.strftime('%Y-%m-%d %H:%M:%S')}'",
            "STOP_TIME": f"'{stop_time.strftime('%Y-%m-%d %H:%M:%S')}'",
            "STEP_SIZE": f"'{step_minutes} m'",
            "TIME_TYPE": "'UT'",
            "TIME_DIGITS": "'MINUTES'",
            "CAL_FORMAT": "'CAL'",
            "QUANTITIES": "'4'",
            "ANG_FORMAT": "'DEG'",
            "EXTRA_PREC": "'YES'",
            "CSV_FORMAT": "'NO'",
            "APPARENT": "'AIRLESS'",
        }

    async def get_site_altaz(
        self,
        *,
        target: str,
        target_name: str,
        latitude_deg: float,
        longitude_deg: float,
        elevation_m: float | None,
        start_time: datetime,
        stop_time: datetime,
        step_minutes: int,
    ) -> list[EphemerisPoint]:
        params = self.build_params(
            target=target,
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            elevation_m=elevation_m,
            start_time=start_time,
            stop_time=stop_time,
            step_minutes=step_minutes,
        )
        text = await self._request(params, target_name=target_name)

        try:
            return parse_altaz_table(text)
        except HorizonsParseError as exc:
            raise UpstreamServiceError(
                f"Could not parse JPL Horizons response for {target_name}.",
                details={
                    "service": "JPL Horizons",
                    "target": target_name,
                    "reason": str(exc),
                },
            ) from exc

    async def _request(self, params: dict[str, str], *, target_name: str) -> str:
        headers = {"User-Agent": self.user_agent, "Accept": "text/plain"}
        last_error: Exception | None = None

        async with self._semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(
                        timeout=self.timeout_seconds,
                        transport=self._transport,
                        headers=headers,
                    ) as client:
                        response = await client.get(self.base_url, params=params)

                    if response.status_code >= 500 and attempt < self.max_retries:
                        logger.warning(
                            "JPL Horizons returned HTTP %s for %s; retrying",
                            response.status_code,
                            target_name,
                        )
                        await asyncio.sleep(0.4 * (attempt + 1))
                        continue

                    response.raise_for_status()
                    return response.text
                except httpx.TimeoutException as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.4 * (attempt + 1))
                        continue
                except httpx.HTTPStatusError as exc:
                    raise UpstreamServiceError(
                        f"JPL Horizons returned HTTP {exc.response.status_code} for {target_name}.",
                        details={
                            "service": "JPL Horizons",
                            "target": target_name,
                            "status_code": exc.response.status_code,
                        },
                    ) from exc
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.4 * (attempt + 1))
                        continue

        if isinstance(last_error, httpx.TimeoutException):
            raise UpstreamTimeoutError(
                f"JPL Horizons timed out while requesting {target_name}.",
                details={"service": "JPL Horizons", "target": target_name},
            ) from last_error

        raise UpstreamServiceError(
            f"Could not reach JPL Horizons for {target_name}.",
            details={
                "service": "JPL Horizons",
                "target": target_name,
                "reason": str(last_error) if last_error else "unknown error",
            },
        ) from last_error
