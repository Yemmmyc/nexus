"""Incident retrieval and Phase 2 evidence-grounded investigation routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import InvestigationOrchestrator
from app.db.database import get_db
from app.schemas.investigation import (
    EvidenceBundle,
    IncidentTimelineResponse,
    InvestigationResult,
)
from app.schemas.simulation import DetectedIncident, IncidentListResponse
from app.services.incident_repository import (
    build_incident_timeline,
    get_persisted_evidence_bundle,
    get_persisted_incident,
    get_persisted_investigation,
    list_persisted_incidents,
    upsert_incident,
)
from app.services.simulation_service import SimulationController

router = APIRouter(prefix="/incidents", tags=["Incidents & Investigation"])


def _get_controller(request: Request) -> SimulationController:
    return request.app.state.simulation_service


def _get_orchestrator(request: Request) -> InvestigationOrchestrator:
    return request.app.state.investigation_orchestrator


def _resolve_incident(
    incident_id: str, controller: SimulationController, db: Session
) -> DetectedIncident:
    """Resolve an incident from persisted SQLite or live simulator state, syncing if needed."""
    live = controller.get_incident(incident_id)
    if live is not None:
        upsert_incident(db, live, tick_interval_seconds=controller.engine.tick_interval_seconds)
    persisted = get_persisted_incident(db, incident_id)
    if persisted is not None:
        return persisted
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Incident '{incident_id}' not found.",
    )


@router.get("", response_model=IncidentListResponse, summary="List incidents")
def list_incidents(
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    for live in controller.list_incidents():
        upsert_incident(db, live, tick_interval_seconds=controller.engine.tick_interval_seconds)
    return IncidentListResponse(incidents=list_persisted_incidents(db))


@router.get("/{incident_id}", response_model=DetectedIncident, summary="Get incident detail")
def get_incident(
    incident_id: str,
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> DetectedIncident:
    return _resolve_incident(incident_id, controller, db)


@router.post(
    "/{incident_id}/investigate",
    response_model=InvestigationResult,
    summary="Run evidence-grounded investigation for an incident",
)
def investigate_incident(
    incident_id: str,
    controller: SimulationController = Depends(_get_controller),
    orchestrator: InvestigationOrchestrator = Depends(_get_orchestrator),
    db: Session = Depends(get_db),
) -> InvestigationResult:
    incident = _resolve_incident(incident_id, controller, db)
    return orchestrator.run_investigation(
        incident=incident,
        engine=controller.engine,
        db=db,
    )


@router.get(
    "/{incident_id}/investigation",
    response_model=InvestigationResult,
    summary="Retrieve persisted investigation findings",
)
def get_investigation(
    incident_id: str,
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> InvestigationResult:
    _resolve_incident(incident_id, controller, db)
    result = get_persisted_investigation(db, incident_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation for incident '{incident_id}' has not been run yet.",
        )
    return result


@router.get(
    "/{incident_id}/evidence",
    response_model=EvidenceBundle,
    summary="Retrieve traceable evidence bundle for an incident",
)
def get_incident_evidence(
    incident_id: str,
    controller: SimulationController = Depends(_get_controller),
    orchestrator: InvestigationOrchestrator = Depends(_get_orchestrator),
    db: Session = Depends(get_db),
) -> EvidenceBundle:
    incident = _resolve_incident(incident_id, controller, db)
    persisted_bundle = get_persisted_evidence_bundle(db, incident_id)
    if persisted_bundle is not None:
        return persisted_bundle
    return orchestrator.collect_evidence(incident, controller.engine)


@router.get(
    "/{incident_id}/timeline",
    response_model=IncidentTimelineResponse,
    summary="Retrieve chronological incident timeline",
)
def get_incident_timeline(
    incident_id: str,
    controller: SimulationController = Depends(_get_controller),
    db: Session = Depends(get_db),
) -> IncidentTimelineResponse:
    incident = _resolve_incident(incident_id, controller, db)
    entries = build_incident_timeline(db, incident)
    return IncidentTimelineResponse(incident_id=incident.id, entries=entries)
