from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel


class ExternalSource(ApiModel):
    id: str
    name: str
    category: str
    access: str
    status: str
    documentation_url: str
    used_for: str
    notes: str


class SourceListResponse(ApiModel):
    sources: list[ExternalSource]
    total: int
    caveats: list[str] = Field(default_factory=list)
