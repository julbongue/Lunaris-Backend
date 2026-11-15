from datetime import UTC

import pytest

from app.integrations.horizons.parser import HorizonsParseError, parse_altaz_table

# Excerpt from a real JPL Horizons observer table (Earth from a lunar south
# pole site, 2026-11-15, QUANTITIES='4'). Kept short for the unit test.
HORIZONS_EXCERPT = """
 Date__(UT)__HR:MN     Azimuth__(a-app)__Elevation
**************************************************
$$SOE
 2026-Nov-15 00:00 *   357.380210632  -3.453000972
 2026-Nov-15 06:00 *   357.034190041  -3.154708604
 2026-Nov-15 12:00 *   356.691547456  -2.847917962
$$EOE
"""


def test_parse_altaz_table():
    points = parse_altaz_table(HORIZONS_EXCERPT)

    assert len(points) == 3
    assert points[0].timestamp.tzinfo == UTC
    assert points[0].timestamp.hour == 0
    assert points[0].azimuth_deg == pytest.approx(357.380210632)
    assert points[0].elevation_deg == pytest.approx(-3.453000972)
    assert points[2].timestamp.hour == 12


def test_parse_altaz_table_requires_markers():
    with pytest.raises(HorizonsParseError):
        parse_altaz_table("No table here")


def test_parse_altaz_table_rejects_empty_table():
    with pytest.raises(HorizonsParseError):
        parse_altaz_table("$$SOE\n$$EOE")


def test_parse_altaz_table_normalizes_azimuth():
    text = """
$$SOE
 2026-Nov-15 00:00 *   360.5   1.0
$$EOE
"""
    points = parse_altaz_table(text)
    assert points[0].azimuth_deg == pytest.approx(0.5)
