"""Root API v1 router aggregation."""

from fastapi import APIRouter

from app.api import audit, health, incidents, remediations, simulation, topology

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(simulation.router)
api_v1_router.include_router(topology.router)
api_v1_router.include_router(incidents.router)
api_v1_router.include_router(remediations.router)
api_v1_router.include_router(audit.router)

