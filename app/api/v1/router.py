from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    health,
    scenarios,
    sites,
    sources,
    topography,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(sites.router)
api_router.include_router(analysis.router)
api_router.include_router(scenarios.router)
api_router.include_router(topography.router)
api_router.include_router(sources.router)
