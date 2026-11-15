from __future__ import annotations

from typing import Any


class LunarisError(Exception):
    """Base class for errors that map to an API response."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(LunarisError):
    status_code = 404
    code = "not_found"


class BadRequestError(LunarisError):
    status_code = 400
    code = "bad_request"


class UpstreamServiceError(LunarisError):
    status_code = 502
    code = "upstream_error"


class UpstreamTimeoutError(UpstreamServiceError):
    status_code = 504
    code = "upstream_timeout"


class EngineUnavailableError(LunarisError):
    status_code = 501
    code = "engine_unavailable"


class DatabaseUnavailableError(LunarisError):
    status_code = 503
    code = "database_unavailable"
