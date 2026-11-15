from __future__ import annotations

import json
from pathlib import Path

from app.schemas.sources import ExternalSource, SourceListResponse

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sources.json"

SOURCE_CAVEATS = [
    "Integration status reflects the access mechanisms verified for this MVP. "
    "External services may change their endpoints or terms.",
    "CSA Moon Exploration is a reference portal and is intentionally not queried at runtime.",
]


class SourceService:
    def __init__(self, sources: list[ExternalSource]) -> None:
        self._sources = sources

    @classmethod
    def from_file(cls, path: Path = DATA_PATH) -> SourceService:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls([ExternalSource.model_validate(entry) for entry in payload["sources"]])

    def list_sources(self) -> SourceListResponse:
        return SourceListResponse(
            sources=list(self._sources),
            total=len(self._sources),
            caveats=list(SOURCE_CAVEATS),
        )
