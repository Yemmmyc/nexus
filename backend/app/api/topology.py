"""Topology and telemetry API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.schemas.telemetry import TelemetryHistoryResponse
from app.schemas.topology import TopologyResponse
from app.services.simulation_service import SimulationController

router = APIRouter(tags=["Topology & Telemetry"])


def _get_controller(request: Request) -> SimulationController:
    return request.app.state.simulation_service


@router.get("/topology", response_model=TopologyResponse, summary="Get live service topology")
def get_topology(
    controller: SimulationController = Depends(_get_controller),
) -> TopologyResponse:
    return controller.get_topology()


@router.get(
    "/telemetry",
    response_model=TelemetryHistoryResponse,
    summary="Get latest telemetry for all services or one service",
)
def get_latest_telemetry(
    service_id: str | None = Query(default=None),
    controller: SimulationController = Depends(_get_controller),
) -> TelemetryHistoryResponse:
    try:
        samples = controller.get_latest_telemetry(service_id=service_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TelemetryHistoryResponse(tick=controller.engine.tick, samples=samples)


@router.get(
    "/telemetry/history",
    response_model=TelemetryHistoryResponse,
    summary="Get recent telemetry history",
)
def get_telemetry_history(
    service_id: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=120),
    controller: SimulationController = Depends(_get_controller),
) -> TelemetryHistoryResponse:
    try:
        samples = controller.get_telemetry_history(service_id=service_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TelemetryHistoryResponse(tick=controller.engine.tick, samples=samples)

