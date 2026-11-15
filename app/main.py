from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import LunarisError

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

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

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description=settings.app_description,
    openapi_tags=TAGS_METADATA,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)


@app.exception_handler(LunarisError)
async def lunaris_exception_handler(
    request: Request,
    exc: LunarisError,
) -> JSONResponse:
    logging.getLogger("lunaris").info(
        "Handled %s on %s: %s", exc.code, request.url.path, exc.message
    )
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


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "message": "Welcome to LUNARIS API",
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
