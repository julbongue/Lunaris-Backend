from __future__ import annotations

from app.core.exceptions import EngineUnavailableError
from app.services.engine.base import ScientificEngine
from app.services.engine.geometric import GeometricEngine
from app.services.engine.scientific_adapter import ScientificAdapter
from app.services.engine.ephemeris_provider import MockDeterministicEphemerisProvider


def _default_engines() -> dict[str, object]:
    return {
        "geometric": GeometricEngine(),
        "scientific-lunaris": ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider()),
    }


_ENGINES: dict[str, object] = _default_engines()


def get_engine(name: str) -> object:
    # allow lazy refresh if needed
    if name == "scientific-lunaris" and name not in _ENGINES:
        _ENGINES[name] = ScientificAdapter(ephemeris_provider=MockDeterministicEphemerisProvider())
    engine = _ENGINES.get(name)
    if engine is None:
        available = ", ".join(sorted(_ENGINES))
        raise EngineUnavailableError(
            f"Scientific engine '{name}' is not available.",
            details={"requested": name, "available": available},
        )
    return engine


def register_engine(name: str, engine: object) -> None:
    _ENGINES[name] = engine
