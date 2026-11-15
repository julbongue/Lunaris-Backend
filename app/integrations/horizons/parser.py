from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

_DATE_PATTERN = re.compile(
    r"^\s*(?P<date>\d{4}-[A-Za-z]{3}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)\s*(?P<rest>.*)$"
)
_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


class HorizonsParseError(ValueError):
    """Raised when a Horizons table cannot be parsed safely."""


@dataclass(frozen=True)
class EphemerisPoint:
    timestamp: datetime
    azimuth_deg: float
    elevation_deg: float


def _parse_timestamp(date_text: str, time_text: str) -> datetime:
    combined = f"{date_text} {time_text}"
    for fmt in ("%Y-%b-%d %H:%M:%S.%f", "%Y-%b-%d %H:%M:%S", "%Y-%b-%d %H:%M"):
        try:
            return datetime.strptime(combined, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise HorizonsParseError(f"Unrecognized Horizons timestamp: {combined!r}")


def parse_altaz_table(text: str) -> list[EphemerisPoint]:
    """Parse a Horizons OBSERVER table containing QUANTITIES='4' (Az/El).

    The parser deliberately requires the $$SOE/$$EOE markers. It never
    interpolates or fabricates values when the table is missing.
    """

    start = text.find("$$SOE")
    stop = text.find("$$EOE")
    if start == -1 or stop == -1 or stop <= start:
        snippet = " ".join(text.strip().splitlines()[:4])[:300]
        raise HorizonsParseError(
            "Horizons response does not contain a $$SOE/$$EOE observer table. "
            f"Response excerpt: {snippet!r}"
        )

    points: list[EphemerisPoint] = []
    for raw_line in text[start + len("$$SOE") : stop].splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _DATE_PATTERN.match(line)
        if match is None:
            raise HorizonsParseError(f"Unrecognized Horizons table row: {line!r}")

        numbers = [float(value) for value in _NUMBER_PATTERN.findall(match.group("rest"))]
        if len(numbers) < 2:
            raise HorizonsParseError(f"Horizons row has no Az/El values: {line!r}")

        azimuth_deg = numbers[-2] % 360.0
        elevation_deg = numbers[-1]
        if not -90.0 <= elevation_deg <= 90.0:
            raise HorizonsParseError(f"Horizons elevation outside [-90, 90] in row: {line!r}")

        points.append(
            EphemerisPoint(
                timestamp=_parse_timestamp(match.group("date"), match.group("time")),
                azimuth_deg=azimuth_deg,
                elevation_deg=elevation_deg,
            )
        )

    if not points:
        raise HorizonsParseError("Horizons observer table is empty")

    points.sort(key=lambda point: point.timestamp)
    return points
