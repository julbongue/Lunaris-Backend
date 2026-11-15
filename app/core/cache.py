from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Hashable


class TTLCache[K: Hashable, V]:
    """Small in-process TTL cache for external ephemeris requests.

    The cache is intentionally process-local. For the hackathon MVP it avoids
    repeated JPL Horizons calls while keeping deployment simple. A shared
    cache (Redis, etc.) can replace it later behind the same interface.
    """

    def __init__(self, ttl_seconds: float, max_entries: int = 256) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() >= expires_at:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return value

    def set(self, key: K, value: V) -> None:
        if key in self._items:
            del self._items[key]
        self._items[key] = (time.monotonic() + self.ttl_seconds, value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
