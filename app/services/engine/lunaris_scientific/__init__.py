"""LUNARIS independent scientific engine core.

This package is developed in isolation from the FastAPI backend. It provides
mathematical and scientific primitives for lunar landing-site analysis:
geometry, coordinate systems, reference-frame transforms, and visibility /
illumination calculations.

Units and conventions are documented in ``docs/scientific/fundamentals.md`` and
module docstrings. Unless stated otherwise:
- Angles: radians internally in some helpers, degrees at public API boundaries.
- Distances: meters (m) or kilometers (km) as documented per field.
- Time: UTC datetimes / ISO-8601 strings in temporal interfaces.
"""

__all__ = [
    "vectors",
    "coordinates",
    "frames",
    "celestial",
    "visibility",
    "illumination",
    "topography",
    "temporal",
]
