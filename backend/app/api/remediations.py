"""Phase 3 policy-gated simulated remediation, approval, execution, and verification routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import InvestigationOrchestrator
from app.db.database import get_db
from app.recovery.catalog import list_catalog_actions
from app.recovery.executor import ExecutionBlockedError, ExecutionStateError
from app.schemas.remediation import (
    ApprovalDecisionRequest,
    CreateRemediationRequest,
    ExecutionRecord,
    RemediationCatalogResponse,
    RemediationPlan,
    RemediationPlanListResponse,
    VerificationResult,
)
from app.services.incident_repository import (
    get_persisted_evidence_bundle,
    get_persisted_incident,
    get_persisted_investigation,
    upsert_incident,
)
from app.services.remediation_repository import RemediationService
from app.services.simulation_service import SimulationController

router = APIRouter(tags=["Remediations & Policy Gate"])


def _get_controller(request: Request) -> SimulationController:
    return request.app.state.simulation_service


def _get_orchestrator(request: Request) -> InvestigationOrchestrator:
    return request.app.state.investigation_orchestrator


def _get_remediation_service(request: Request) -> RemediationService:
    return request.app.state.remediation_service


def _resolve_incident_or_404(
    incident_id: str, controller: SimulationController, db: Session
):
    live = controller.get_incident(incident_id)
    if live is not None:
        upsert_incident(db, live, tick_interval_seconds=controller.engine.tick_interval_seconds)
    inc = get_persisted_incident(db, incident_id)
    if inc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )
    return inc


@router.get(
    "/remediations/catalog",
    response_model=RemediationCatalogResponse,
    summary="List static allowlisted simulated remediation actions",
)
def get_remediation_catalog() -> RemediationCatalogResponse:
    return RemediationCatalogResponse(actions=list_catalog_actions())


@router.get(
    "/remediations",
    response_model=RemediationPlanListResponse,
    summary="List remediation plans",
)
def list_remediation_plans(
    incident_id: str | None = Query(default=None),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlanListResponse:
    return RemediationPlanListResponse(plans=service.list_plans(db, incident_id=incident_id))


@router.get(
    "/remediations/{plan_id}",
    response_model=RemediationPlan,
    summary="Get remediation plan detail",
)
def get_remediation_plan(
    plan_id: str,
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlan:
    plan = service.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found.",
        )
    return plan


@router.post(
    "/incidents/{incident_id}/remediations",
    response_model=RemediationPlan,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a policy-evaluated simulated remediation plan for an incident",
)
def create_remediation_plan(
    incident_id: str,
    payload: CreateRemediationRequest | None = None,
    controller: SimulationController = Depends(_get_controller),
    orchestrator: InvestigationOrchestrator = Depends(_get_orchestrator),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlan:
    incident = _resolve_incident_or_404(incident_id, controller, db)
    investigation = get_persisted_investigation(db, incident_id)
    evidence_bundle = get_persisted_evidence_bundle(db, incident_id)
    if evidence_bundle is None:
        evidence_bundle = orchestrator.collect_evidence(incident, controller.engine)

    return service.create_plan(
        db=db,
        incident=incident,
        investigation=investigation,
        evidence_bundle=evidence_bundle,
        engine=controller.engine,
        override_action_id=payload.action_id if payload else None,
        override_target_service=payload.target_service if payload else None,
        override_parameters=payload.parameters if payload else None,
    )


@router.post(
    "/remediations/{plan_id}/evaluate",
    response_model=RemediationPlan,
    summary="Re-evaluate Trust Agent policy for a remediation plan",
)
def evaluate_remediation_plan(
    plan_id: str,
    controller: SimulationController = Depends(_get_controller),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlan:
    existing = service.get_plan(db, plan_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found.",
        )
    incident = _resolve_incident_or_404(existing.incident_id, controller, db)
    investigation = get_persisted_investigation(db, existing.incident_id)
    try:
        return service.evaluate_plan_policy(
            db=db,
            plan_id=plan_id,
            incident=incident,
            investigation=investigation,
            engine=controller.engine,
        )
    except ExecutionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/remediations/{plan_id}/approve",
    response_model=RemediationPlan,
    summary="Human operator approval for a policy-gated remediation plan",
)
def approve_remediation_plan(
    plan_id: str,
    payload: ApprovalDecisionRequest | None = None,
    controller: SimulationController = Depends(_get_controller),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlan:
    decision = payload or ApprovalDecisionRequest()
    try:
        return service.approve_plan(
            db=db,
            plan_id=plan_id,
            actor=decision.actor,
            comment=decision.comment,
            engine=controller.engine,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExecutionBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ExecutionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/remediations/{plan_id}/reject",
    response_model=RemediationPlan,
    summary="Human operator rejection for a policy-gated remediation plan",
)
def reject_remediation_plan(
    plan_id: str,
    payload: ApprovalDecisionRequest | None = None,
    controller: SimulationController = Depends(_get_controller),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlan:
    decision = payload or ApprovalDecisionRequest()
    try:
        return service.reject_plan(
            db=db,
            plan_id=plan_id,
            actor=decision.actor,
            comment=decision.comment,
            engine=controller.engine,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExecutionBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ExecutionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/remediations/{plan_id}/execute",
    response_model=RemediationPlan,
    summary="Execute an approved or auto-approved simulated remediation plan",
)
def execute_remediation_plan(
    plan_id: str,
    controller: SimulationController = Depends(_get_controller),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> RemediationPlan:
    existing = service.get_plan(db, plan_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found.",
        )
    incident = _resolve_incident_or_404(existing.incident_id, controller, db)
    try:
        return service.execute_plan(
            db=db,
            plan_id=plan_id,
            incident=incident,
            engine=controller.engine,
        )
    except ExecutionBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ExecutionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/remediations/{plan_id}/execution",
    response_model=ExecutionRecord,
    summary="Retrieve simulated remediation execution record",
)
def get_remediation_execution(
    plan_id: str,
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> ExecutionRecord:
    plan = service.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found.",
        )
    if plan.execution_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' has not been executed yet.",
        )
    return plan.execution_record


@router.get(
    "/remediations/{plan_id}/verification",
    response_model=VerificationResult,
    summary="Evaluate and retrieve Verification Agent SLO recovery status",
)
def get_remediation_verification(
    plan_id: str,
    controller: SimulationController = Depends(_get_controller),
    service: RemediationService = Depends(_get_remediation_service),
    db: Session = Depends(get_db),
) -> VerificationResult:
    existing = service.get_plan(db, plan_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan '{plan_id}' not found.",
        )
    incident = _resolve_incident_or_404(existing.incident_id, controller, db)
    try:
        return service.verify_plan(
            db=db,
            plan_id=plan_id,
            incident=incident,
            engine=controller.engine,
        )
    except ExecutionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

