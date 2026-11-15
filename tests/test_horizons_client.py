import asyncio
from datetime import UTC, datetime

import httpx

from app.integrations.horizons import HorizonsClient

TABLE = """
$$SOE
 2026-Nov-15 00:00 *   100.000000000   1.500000000
 2026-Nov-15 06:00 *   101.000000000   2.500000000
$$EOE
"""


def test_horizons_client_builds_lunar_topocentric_request():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, text=TABLE)

    client = HorizonsClient(
        "https://example.test/horizons.api",
        transport=httpx.MockTransport(handler),
    )
    points = asyncio.run(
        client.get_site_altaz(
            target="399",
            target_name="Earth",
            latitude_deg=-42.13,
            longitude_deg=-42.13,
            elevation_m=0.0,
            start_time=datetime(2026, 11, 15, tzinfo=UTC),
            stop_time=datetime(2026, 11, 16, tzinfo=UTC),
            step_minutes=360,
        )
    )

    assert len(points) == 2
    assert captured["COMMAND"] == "'399'"
    assert captured["CENTER"] == "'coord@301'"
    assert captured["COORD_TYPE"] == "'GEODETIC'"
    assert captured["QUANTITIES"] == "'4'"
    assert captured["STEP_SIZE"] == "'360 m'"
    # Negative west longitude must be converted to the 0-360 east convention.
    assert captured["SITE_COORD"] == "'317.87000000,-42.13000000,0.00000000'"
