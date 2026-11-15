"""Temporal analysis utilities for visibility and illumination evolution.

This module provides generic time-stepping and event detection over sampled
states. It does not assume Earth-like day/night cycles; lunar illumination and
visibility periods depend on ephemerides, observer location, and terrain.

Ephemeris positions per instant must be supplied by callers (real data or
explicit synthetic fixtures).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Iterator, Sequence, TypeVar

from .celestial import ensure_utc

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class TimeStep:
    index: int
    time_utc: datetime


@dataclass(frozen=True, slots=True)
class VisibilityWindow:
    start_utc: datetime
    end_utc: datetime  # exclusive in sampling sense
    kind: str  # e.g. "visible", "illuminated"


def iter_time_steps(
    start_utc: datetime,
    stop_utc: datetime,
    step: timedelta,
) -> Iterator[TimeStep]:
    """Yield observation instants in [start, stop) with fixed step."""
    start = ensure_utc(start_utc)
    stop = ensure_utc(stop_utc)
    if step.total_seconds() <= 0:
        raise ValueError("step must be positive")
    if stop <= start:
        raise ValueError("stop_utc must be after start_utc")
    t = start
    i = 0
    while t < stop:
        yield TimeStep(index=i, time_utc=t)
        i += 1
        t = start + i * step


def sample_series(
    start_utc: datetime,
    stop_utc: datetime,
    step: timedelta,
    evaluator: Callable[[datetime], T],
) -> list[tuple[datetime, T]]:
    return [(ts.time_utc, evaluator(ts.time_utc)) for ts in iter_time_steps(start_utc, stop_utc, step)]


def detect_boolean_windows(
    samples: Sequence[tuple[datetime, bool]],
    *,
    kind: str = "visible",
) -> list[VisibilityWindow]:
    """Detect contiguous True intervals from ordered samples.

    Note: interval end is the timestamp of first False sample (or last sample
    boundary context not included); callers may refine with interpolation/root
    finding when higher precision rise/set times are required.
    """
    windows: list[VisibilityWindow] = []
    open_start: datetime | None = None
    prev_t: datetime | None = None
    for t, state in samples:
        if state and open_start is None:
            open_start = t
        if (not state) and open_start is not None:
            windows.append(VisibilityWindow(start_utc=open_start, end_utc=t, kind=kind))
            open_start = None
        prev_t = t
    if open_start is not None and prev_t is not None:
        # open-ended at last sample; represent as ending at last sample time
        windows.append(VisibilityWindow(start_utc=open_start, end_utc=prev_t, kind=kind))
    return windows
