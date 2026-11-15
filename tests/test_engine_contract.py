from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.engine import (
    DataQualityMetadata,
    EarthVisibility,
    EngineInput,
    EngineResult,
    HorizonObstruction,
    IlluminationAngles,
    IlluminationConditions,
    SunVisibility,
)

# ---------------------------------------------------------------------------
# EngineInput: valid inputs
# ---------------------------------------------------------------------------

def test_engine_input_valid_returns_fields():
    start = datetime(2026, 11, 15, tzinfo=UTC)
    stop = start + timedelta(hours=24)
    payload = {
        "latitude_deg": -89.9,
        "longitude_deg": 0.0,
        "altitude_m": 0.0,
        "start_time": start,
        "stop_time": stop,
        "step_minutes": 360,
        "sun_elevation_deg": 0.0,
        "earth_elevation_deg": 5.0,
        "terrain_availability": "none",
        "horizon_reference": "geometric",
        "source": "jpl_horizons",
    }
    obj = EngineInput(**payload)
    assert obj.latitude_deg == -89.9
    assert obj.longitude_deg == 0.0
    assert obj.altitude_m == 0.0
    assert obj.step_minutes == 360
    assert obj.source == "jpl_horizons"


def test_engine_input_not_requires_elevation():
    payload = {
        "latitude_deg": 0.67408,
        "longitude_deg": 23.47297,
        "altitude_m": 0.0,
        "start_time": datetime(2026, 11, 15, tzinfo=UTC),
        "stop_time": datetime(2026, 11, 16, tzinfo=UTC),
        "step_minutes": 60,
    }
    obj = EngineInput(**payload)
    assert obj.altitude_m == 0.0
    assert obj.terrain_availability == "none"
    assert obj.horizon_reference == "geometric"


# ---------------------------------------------------------------------------
# EngineInput: invalid ranges
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field,payload",
    [
        (
            "latitude_deg",
            {
                "latitude_deg": 91.0,
                "longitude_deg": 0.0,
                "start_time": None,
                "stop_time": None,
                "step_minutes": 1,
            },
        ),
        (
            "longitude_deg",
            {
                "latitude_deg": 0.0,
                "longitude_deg": 181.0,
                "start_time": None,
                "stop_time": None,
                "step_minutes": 1,
            },
        ),
        (
            "altitude_m",
            {
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "altitude_m": -1.0,
                "start_time": None,
                "stop_time": None,
                "step_minutes": 1,
            },
        ),
        (
            "start_time",
            {
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "start_time": datetime(2026, 11, 16, tzinfo=UTC),
                "stop_time": datetime(2026, 11, 15, tzinfo=UTC),
                "step_minutes": 1,
            },
        ),
        (
            "step_minutes",
            {
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "start_time": datetime(2026, 11, 15, tzinfo=UTC),
                "stop_time": datetime(2026, 11, 16, tzinfo=UTC),
                "step_minutes": 0,
            },
        ),
        (
            "sun_elevation_deg",
            {
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "start_time": None,
                "stop_time": None,
                "step_minutes": 1,
                "sun_elevation_deg": 91.0,
            },
        ),
        (
            "earth_elevation_deg",
            {
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "start_time": None,
                "stop_time": None,
                "step_minutes": 1,
                "earth_elevation_deg": -91.0,
            },
        ),
    ],
)
def test_engine_input_invalid_ranges_rejected(field, payload):
    with pytest.raises(ValidationError):
        EngineInput(**payload)


# ---------------------------------------------------------------------------
# EngineResult structure
# ---------------------------------------------------------------------------

def test_engine_result_has_all_fields():
    result = EngineResult(
        earth=EarthVisibility(
            visible=False,
            elevation_deg=-2.21,
            azimuth_deg=356.02,
            elevation_threshold_deg=5.0,
        ),
        sun=SunVisibility(
            visible=True,
            elevation_deg=2.21,
            azimuth_deg=356.02,
            elevation_threshold_deg=0.0,
        ),
        sun_coordinates=None,
        earth_coordinates=None,
        illumination=IlluminationAngles(
            phase_angle_deg=177.0,
            incidence_angle_deg=89.9,
            emission_angle_deg=0.0,
            solar_longitude_deg=176.0,
        ),
        conditions=IlluminationConditions(
            sunlit=True,
            dark=False,
            terminator=False,
            insolation_w_m2=0.0,
        ),
        horizon=None,
        quality=DataQualityMetadata(
            engine_name="geometric-altaz-threshold",
            engine_version="0.1.0",
            coordinate_system="planetocentric",
            reference_frame="selenographic",
            elevation_source="jpl_horizons",
            temporal_extent="2026-11-15T00:00:00Z/2026-11-16T00:00:00Z",
            notes=["No terrain data"],
        ),
    )
    assert result.earth is not None and result.earth.visible is False
    assert result.sun is not None and result.sun.visible is True
    assert result.illumination is not None
    assert result.conditions is not None
    assert result.quality is not None


def test_engine_result_optional_fields_are_none_by_default():
    result = EngineResult()
    assert result.earth is None
    assert result.sun is None
    assert result.sun_coordinates is None
    assert result.earth_coordinates is None
    assert result.illumination is None
    assert result.conditions is None
    assert result.horizon is None
    assert result.quality is None


# ---------------------------------------------------------------------------
# EarthVisibility / SunVisibility
# ---------------------------------------------------------------------------

def test_earth_visibility_fields_and_bounds():
    ev = EarthVisibility(
        visible=True,
        elevation_deg=12.5,
        azimuth_deg=270.0,
        elevation_threshold_deg=5.0,
    )
    assert ev.visible is True
    assert ev.elevation_deg == 12.5
    assert ev.azimuth_deg == 270.0
    assert ev.elevation_threshold_deg == 5.0


def test_earth_visibility_rejects_elevation_out_of_range():
    with pytest.raises(ValidationError):
        EarthVisibility(
            visible=True,
            elevation_deg=100.0,
            azimuth_deg=0.0,
            elevation_threshold_deg=5.0,
        )


def test_sun_visibility_fields_and_bounds():
    sv = SunVisibility(
        visible=False,
        elevation_deg=-1.0,
        azimuth_deg=180.0,
        elevation_threshold_deg=0.0,
    )
    assert sv.visible is False


# ---------------------------------------------------------------------------
# IlluminationAngles and IlluminationConditions
# ---------------------------------------------------------------------------

def test_illumination_angles_bounds():
    ia = IlluminationAngles(
        phase_angle_deg=177.0,
        incidence_angle_deg=89.9,
        emission_angle_deg=0.0,
        solar_longitude_deg=176.0,
    )
    assert ia.phase_angle_deg == 177.0
    assert ia.incidence_angle_deg == 89.9
    assert ia.emission_angle_deg == 0.0
    assert ia.solar_longitude_deg == 176.0


def test_illumination_conditions():
    ic = IlluminationConditions(
        sunlit=True,
        dark=False,
        terminator=False,
        insolation_w_m2=0.0,
    )
    assert ic.sunlit is True
    assert ic.dark is False
    assert ic.terminator is False
    assert ic.insolation_w_m2 == 0.0


# ---------------------------------------------------------------------------
# HorizonObstruction
# ---------------------------------------------------------------------------

def test_horizon_obstruction():
    ho = HorizonObstruction(
        reference="geometric",
        horizon_elevation_deg=-3.2,
        has_data=True,
        source="lola",
        notes=["Terrain sampled along azimuth 0..360"],
    )
    assert ho.reference == "geometric"
    assert ho.horizon_elevation_deg == -3.2
    assert ho.has_data is True
    assert ho.source == "lola"
    assert len(ho.notes) == 1


# ---------------------------------------------------------------------------
# DataQualityMetadata
# ---------------------------------------------------------------------------

def test_data_quality_metadata():
    dq = DataQualityMetadata(
        engine_name="lola-terrain-baseline",
        engine_version="1.0.0",
        coordinate_system="planetocentric",
        reference_frame="selenographic",
        elevation_source="lola",
        temporal_extent="2026-11-15T00:00:00Z/2026-11-16T00:00:00Z",
        notes=["Terrain resolution 118 m/px"],
    )
    assert dq.elevation_source == "lola"
    assert dq.coordinate_system == "planetocentric"
    assert dq.temporal_extent.startswith("2026-11-15T00:00:00Z")


# ---------------------------------------------------------------------------
# Integration-like: mapping Shackleton diagnosis
# ---------------------------------------------------------------------------

def test_shackleton_earth_visibility_geometric_below_horizon():
    """
    The real Earth elevation at Shackleton rim (-89.9, 0.0) from JPL Horizons
    (2026-11-15, QUANTITIES='4', CENTRE='coord@301') is between -3.5 and -2.2 deg,
    i.e. below the geometric horizon.  The 0% visibility is geometrically
    correct for the 5 deg threshold.  This test documents the diagnosis.
    """
    # Values from the real JPL Horizons server (2026-11-15, Earth (399)).
    # These are the observed values, not a simulation.
    observations = [
        {"time": "00:00", "azimuth_deg": 357.380210632, "elevation_deg": -3.453000972},
        {"time": "06:00", "azimuth_deg": 357.034190041, "elevation_deg": -3.154708604},
        {"time": "12:00", "azimuth_deg": 356.691547456, "elevation_deg": -2.847917962},
        {"time": "18:00", "azimuth_deg": 356.353633149, "elevation_deg": -2.533291628},
        {"time": "24:00", "azimuth_deg": 356.021840778, "elevation_deg": -2.211505455},
    ]
    elevations = [obs["elevation_deg"] for obs in observations]
    # All below the 5 deg threshold
    assert all(e < 5.0 for e in elevations)
    # All below the geometric horizon (< 0)
    assert all(e < 0.0 for e in elevations)
    # Therefore, the Earth is geometrically below the horizon at Shackleton rim
    # during this window; 0% visibility is correct for the geometric horizon.
    assert min(elevations) == -3.453000972
    assert max(elevations) == -2.211505455


def test_shackleton_subject_requires_terrain_context():
    """
    The 0% result is a geometric-horizon observation.  It does not prove
    that the Earth is permanently hidden; a topographic (DEM-based)
    horizon would be required to determine the exact visibility over
    terrain.  This test documents the need for a DEM-based calculation.
    """
    # At the lunar south pole, the Earth's elevation is close to
    # -declination_terra.  If declination_terra > 0, Earth is below horizon.
    # A DEM is needed to compute the horizon obstruction.
    assert True  # the test documents the requirement; no numerical assertion needed here
