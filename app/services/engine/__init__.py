from __future__ import annotations

from app.schemas.engine import (
    CelestialCoordinates,
    DataQualityMetadata,
    EarthVisibility,
    ElevationReference,
    EngineInput,
    EngineResult,
    IlluminationAngles,
    IlluminationConditions,
    ReferenceFrame,
    SunVisibility,
)
from app.services.engine.base import EngineOutput, ScientificEngine
from app.services.engine.geometric import GeometricEngine
from app.services.engine.scientific_adapter import ScientificAdapter
from app.services.engine.registry import get_engine

__all__ = [
    # Legacy (backward compatible)
    "EngineInput",
    "EngineOutput",
    "GeometricEngine",
    "ScientificEngine",
    "ScientificAdapter",
    "get_engine",
    # Definitive contract (new)
    "CelestialCoordinates",
    "DataQualityMetadata",
    "EarthVisibility",
    "EngineResult",
    "ElevationReference",
    "IlluminationAngles",
    "IlluminationConditions",
    "ReferenceFrame",
    "SunVisibility",
]
