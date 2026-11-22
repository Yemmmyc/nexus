"""Simulation control API routes (/api/v1/simulation/*)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.simulation import (
    AdvanceTicksRequest,
    InjectScenarioRequest,
    ResetSimulationRequest,
    ScenarioListResponse,
    SimulationStatusResponse,
)
from app.services.simulation_service import SimulationController

router = APIRouter(prefix="/simulation", tags=["Simulation"])


def _get_controller(request: Request) -> SimulationController:
    return request.app.state.simulation_service


@router.get("/status", response_model=SimulationStatusResponse, summary="Get simulation status")
def get_simulation_status(
    controller: SimulationController = Depends(_get_controller),
) -> SimulationStatusResponse:
    return controller.get_status()


@router.get("/scenarios", response_model=ScenarioListResponse, summary="List fault scenarios")
def list_scenarios(
    controller: SimulationController = Depends(_get_controller),
) -> ScenarioListResponse:
    return ScenarioListResponse(scenarios=controller.list_scenarios())


@router.post("/start", response_model=SimulationStatusResponse, summary="Start simulation loop")
async def start_simulation(
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> SimulationStatusResponse:
    return await controller.start(db=db)


@router.post("/stop", response_model=SimulationStatusResponse, summary="Stop simulation loop")
async def stop_simulation(
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> SimulationStatusResponse:
    return await controller.stop(db=db)


@router.post(
    "/inject",
    response_model=SimulationStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inject a failure scenario",
)
def inject_scenario(
    payload: InjectScenarioRequest,
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> SimulationStatusResponse:
    try:
        _, sim_status = controller.inject_scenario(payload.scenario_id, db=db)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return sim_status


@router.post(
    "/advance",
    response_model=SimulationStatusResponse,
    summary="Deterministically advance simulation by N ticks",
)
def advance_simulation(
    payload: AdvanceTicksRequest,
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> SimulationStatusResponse:
    return controller.advance(ticks=payload.ticks, db=db)


@router.post("/reset", response_model=SimulationStatusResponse, summary="Reset simulation state")
async def reset_simulation(
    payload: ResetSimulationRequest | None = None,
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> SimulationStatusResponse:
    clear_incidents = True if payload is None else payload.clear_incidents
    return await controller.reset(clear_incidents=clear_incidents, db=db)

