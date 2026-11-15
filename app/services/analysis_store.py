from __future__ import annotations

import time
from collections import OrderedDict

from app.schemas.analysis import AnalysisResult


class AnalysisStore:
    """Process-local TTL store for analysis results.

    This is a cache, not a database. Results disappear on restart or expiry.
    """

    def __init__(self, ttl_seconds: int, max_entries: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, AnalysisResult]] = OrderedDict()

    def put(self, result: AnalysisResult) -> None:
        self._purge()
        self._items[result.analysis_id] = (
            time.monotonic() + self._ttl_seconds,
            result,
        )
        self._items.move_to_end(result.analysis_id)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def get(self, analysis_id: str) -> AnalysisResult | None:
        self._purge()
        item = self._items.get(analysis_id)
        if item is None:
            return None
        self._items.move_to_end(analysis_id)
        return item[1]

    def clear(self) -> None:
        self._items.clear()

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [
            analysis_id for analysis_id, (expires_at, _) in self._items.items() if expires_at <= now
        ]
        for analysis_id in expired:
            del self._items[analysis_id]
