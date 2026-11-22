"""Root API v1 router aggregation."""

from fastapi import APIRouter

from app.api import health, incidents, simulation, topology

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(simulation.router)
api_v1_router.include_router(topology.router)
api_v1_router.include_router(incidents.router)

