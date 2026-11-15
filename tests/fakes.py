from __future__ import annotations

from datetime import datetime, timedelta

from app.integrations.horizons import EphemerisPoint


class FakeHorizonsClient:
    """Deterministic test double; never used by the production app."""

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
        del target_name, latitude_deg, longitude_deg, elevation_m

        total_minutes = int((stop_time - start_time).total_seconds() / 60)
        count = total_minutes // step_minutes + 1
        points: list[EphemerisPoint] = []

        for index in range(count):
            timestamp = start_time + timedelta(minutes=index * step_minutes)
            if target == "10":
                elevation = 8.0 if index % 3 != 0 else -4.0
            else:
                elevation = 6.0 if index % 2 == 0 else -2.0
            points.append(
                EphemerisPoint(
                    timestamp=timestamp,
                    azimuth_deg=(90.0 + index * 5.0) % 360.0,
                    elevation_deg=elevation,
                )
            )
        return points
