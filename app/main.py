from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import LunarisError
from app.services.sites import SiteService
from app.services.sources import SourceService
from app.services.topography import TopographyService

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=settings.log_level.upper(), format=LOG_FORMAT)
    else:
        root.setLevel(settings.log_level.upper())


configure_logging()
logger = logging.getLogger("lunaris")

TAGS_METADATA = [
    {"name": "Health", "description": "Service liveness and configuration summary."},
    {"name": "Sites", "description": "Curated lunar sites and custom coordinates."},
    {
        "name": "Analysis",
        "description": "Sampled Sun/Earth geometry, visibility windows and summaries.",
    },
    {"name": "Scenarios", "description": "Compare multiple sites and date ranges."},
    {"name": "Topography", "description": "Verified external map-layer context."},
    {"name": "Sources", "description": "External data-source integration status."},
    {"name": "Root", "description": "API entry point."},
]


def validate_runtime_configuration() -> None:
    if "*" in settings.cors_origins:
        raise RuntimeError(
            "CORS_ORIGINS must not include '*' because wildcard origins are not allowed."
        )
    if not settings.api_v1_prefix.startswith("/"):
        raise RuntimeError("API_V1_PREFIX must start with '/'.")
    if settings.port < 1 or settings.port > 65535:
        raise RuntimeError("PORT must be between 1 and 65535.")

    # Verify essential local data/resources used by the API.
    SiteService.from_file().list_sites()
    SourceService.from_file().list_sources()
    from app.integrations.lroc import LrocWmsClient
    from app.integrations.moontrek import MoonTrekClient

    TopographyService.from_file(
        lroc=LrocWmsClient(settings.lroc_wms_url),
        moontrek=MoonTrekClient(settings.moontrek_tiles_url),
        settings=settings,
    ).list_layers()

    logger.info(
        "Runtime configuration validated (engine=%s, api=%s, cors_origins=%s)",
        settings.scientific_engine,
        settings.api_v1_prefix,
        len(settings.cors_origins),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    validate_runtime_configuration()
    logger.info("Application startup complete.")
    try:
        yield
    finally:
        logger.info("Application shutdown: closing cached resources.")
        try:
            from app.api import deps

            deps.get_ephemeris_cache.cache_clear()
            deps.get_analysis_store.cache_clear()
        except Exception:  # pragma: no cover - defensive shutdown
            logger.exception("Failed to clear in-memory caches during shutdown.")


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max(0, int(max_bytes))

    async def dispatch(self, request: Request, call_next):
        if self.max_bytes <= 0 or request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "request_too_large",
                                "message": "Request body exceeds the configured size limit.",
                                "details": {"max_bytes": self.max_bytes},
                            }
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.requests = max(1, int(requests))
        self.window_seconds = max(1, int(window_seconds))
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _client_ip(self, request: Request) -> str:
        if settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip() or "unknown"
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)
        now = time.monotonic()
        ip = self._client_ip(request)
        with self._lock:
            bucket = self._hits[ip]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.requests:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "error": {
                            "code": "rate_limited",
                            "message": "Too many requests. Please retry later.",
                            "details": {"retry_after_seconds": retry_after},
                        }
                    },
                )
            bucket.append(now)
        return await call_next(request)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description=settings.app_description,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )

    if settings.max_request_body_bytes > 0:
        app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.exception_handler(LunarisError)
    async def lunaris_exception_handler(request: Request, exc: LunarisError) -> JSONResponse:
        logger.info("Handled %s on %s: %s", exc.code, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s", request.url.path)
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": str(exc),
                        "details": {"type": exc.__class__.__name__},
                    }
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred.",
                    "details": {},
                }
            },
        )

    @app.get("/", tags=["Root"])
    def root() -> dict[str, str]:
        return {
            "message": "Welcome to LUNARIS API",
            "version": settings.app_version,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }

    @app.get("/healthz", tags=["Health"], include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
