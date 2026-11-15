"""Three-dimensional vector operations.

Conventions
-----------
- Vectors are represented as immutable Cartesian triples ``(x, y, z)`` in a
  right-handed coordinate system.
- Components are dimensionless direction components or carry length units (e.g.
  meters, kilometers) depending on context; operations do not attach units.
- Angles returned by this module are in **radians** unless a ``*_deg`` helper
  is used.

The module intentionally avoids external dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class Vec3:
    """Immutable 3D vector."""

    x: float
    y: float
    z: float

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y
        yield self.z

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def __truediv__(self, scalar: float) -> "Vec3":
        if abs(scalar) < EPSILON:
            raise ZeroDivisionError("Division by zero/near-zero scalar")
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)


def vec3(x: float, y: float, z: float) -> Vec3:
    return Vec3(float(x), float(y), float(z))


def dot(a: Vec3, b: Vec3) -> float:
    """Scalar (dot) product."""
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Vector (cross) product, right-handed."""
    return Vec3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    )


def norm(a: Vec3) -> float:
    """Euclidean magnitude."""
    return math.sqrt(dot(a, a))


def normalize(a: Vec3, *, eps: float = EPSILON) -> Vec3:
    """Return unit vector in direction of ``a``.

    Raises ValueError for zero/near-zero vectors.
    """
    n = norm(a)
    if n < eps:
        raise ValueError("Cannot normalize zero/near-zero vector")
    return a / n


def distance(a: Vec3, b: Vec3) -> float:
    """Euclidean distance between points represented by vectors."""
    return norm(a - b)


def angle_between(a: Vec3, b: Vec3, *, eps: float = EPSILON) -> float:
    """Angle between vectors in radians, range [0, pi]."""
    na = norm(a)
    nb = norm(b)
    if na < eps or nb < eps:
        raise ValueError("Cannot compute angle with zero/near-zero vector")
    c = dot(a, b) / (na * nb)
    c = max(-1.0, min(1.0, c))
    return math.acos(c)


def angle_between_deg(a: Vec3, b: Vec3, *, eps: float = EPSILON) -> float:
    return math.degrees(angle_between(a, b, eps=eps))


def is_finite(v: Vec3) -> bool:
    return all(math.isfinite(c) for c in v)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def deg_to_rad(deg: float) -> float:
    return math.radians(deg)


def rad_to_deg(rad: float) -> float:
    return math.degrees(rad)


def normalize_angle_deg(deg: float, period: float = 360.0) -> float:
    """Normalize angle to [0, period)."""
    return deg % period


def normalize_longitude_deg(lon_deg: float) -> float:
    """Normalize longitude to [-180, 180) degrees (east-positive)."""
    x = normalize_angle_deg(lon_deg, 360.0)
    if x >= 180.0:
        x -= 360.0
    return x
