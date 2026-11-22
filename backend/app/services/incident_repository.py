"""SQLite persistence repository for incidents, investigations, and timelines."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AuditLogORM, IncidentORM, InvestigationORM
from app.schemas.investigation import (
    BlastRadiusAssessment,
    ConfidenceAssessment,
    EvidenceBundle,
    EvidenceItem,
    InvestigationResult,
    LogicalAgentTrace,
    ServiceRoleAssessment,
    TimelineEntry,
)
from app.schemas.simulation import DetectedIncident
from app.schemas.telemetry import MonitoringEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_incident(
    db: Session,
    incident: DetectedIncident,
    *,
    tick_interval_seconds: float = 2.0,
) -> IncidentORM:
    """Create or update a persistent IncidentORM record from simulator state."""
    existing = db.get(IncidentORM, incident.id)
    serialized_events = [ev.model_dump(mode="json") for ev in incident.triggering_evidence]
    sim_time_s = round(incident.detected_tick * tick_interval_seconds, 2)

    if existing is None:
        record = IncidentORM(
            id=incident.id,
            title=incident.title,
            scenario_id=incident.scenario_id,
            severity=incident.severity,
            status=incident.status,
            detected_tick=incident.detected_tick,
            detected_sim_time_s=sim_time_s,
            detected_at=incident.detected_at,
            updated_tick=incident.updated_tick,
            updated_at=incident.updated_at,
            root_cause_candidate=incident.root_cause_candidate,
            root_cause_rationale=incident.root_cause_rationale,
            affected_services=list(incident.affected_services),
            supporting_events=serialized_events,
            investigation_status="NOT_STARTED",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    existing.title = incident.title
    existing.severity = incident.severity
    existing.status = incident.status
    existing.updated_tick = incident.updated_tick
    existing.updated_at = incident.updated_at
    existing.root_cause_candidate = incident.root_cause_candidate
    existing.root_cause_rationale = incident.root_cause_rationale
    existing.affected_services = list(incident.affected_services)
    existing.supporting_events = serialized_events
    db.commit()
    db.refresh(existing)
    return existing


def clear_persisted_incidents(db: Session) -> None:
    """Remove persisted incidents and investigations during a clean simulation reset."""
    db.execute(delete(InvestigationORM))
    db.execute(delete(IncidentORM))
    db.commit()


def to_detected_incident(record: IncidentORM) -> DetectedIncident:
    """Convert an IncidentORM row to the API DetectedIncident schema."""
    events = [MonitoringEvent.model_validate(ev) for ev in (record.supporting_events or [])]
    return DetectedIncident(
        id=record.id,
        title=record.title,
        scenario_id=record.scenario_id,
        status=record.status,  # type: ignore[arg-type]
        severity=record.severity,  # type: ignore[arg-type]
        affected_services=list(record.affected_services or []),
        root_cause_candidate=record.root_cause_candidate,
        root_cause_rationale=record.root_cause_rationale,
        triggering_evidence=events,
        detected_tick=record.detected_tick,
        detected_sim_time_s=record.detected_sim_time_s,
        detected_at=record.detected_at,
        updated_tick=record.updated_tick,
        updated_at=record.updated_at,
        investigation_status=record.investigation_status,  # type: ignore[arg-type]
    )


def list_persisted_incidents(db: Session) -> list[DetectedIncident]:
    """Return persisted incidents ordered newest first."""
    rows = (
        db.execute(
            select(IncidentORM).order_by(IncidentORM.detected_tick.desc(), IncidentORM.id.desc())
        )
        .scalars()
        .all()
    )
    return [to_detected_incident(r) for r in rows]


def get_persisted_incident(db: Session, incident_id: str) -> DetectedIncident | None:
    """Retrieve a single persisted incident by ID."""
    row = db.get(IncidentORM, incident_id)
    return to_detected_incident(row) if row is not None else None


def save_investigation(
    db: Session,
    result: InvestigationResult,
    bundle: EvidenceBundle,
) -> InvestigationORM:
    """Persist or update an investigation result for an incident."""
    existing = (
        db.execute(select(InvestigationORM).where(InvestigationORM.incident_id == result.incident_id))
        .scalar_one_or_none()
    )
    now = _utc_now()
    payload = {
        "status": result.status,
        "inference_mode": result.inference_mode,
        "model_name": result.model_name,
        "summary": result.summary,
        "root_cause_hypothesis": result.root_cause_hypothesis,
        "probable_root_cause_service": result.probable_root_cause_service,
        "supporting_evidence": [e.model_dump(mode="json") for e in result.supporting_evidence],
        "limiting_evidence": list(result.limiting_evidence),
        "affected_services": list(result.affected_services),
        "service_roles": [r.model_dump(mode="json") for r in result.service_roles],
        "contributing_factors": list(result.contributing_factors),
        "blast_radius": result.blast_radius.model_dump(mode="json"),
        "confidence": result.confidence.model_dump(mode="json"),
        "recommended_next_steps": list(result.recommended_next_steps),
        "agent_trace": [t.model_dump(mode="json") for t in result.agent_trace],
        "evidence_bundle": bundle.model_dump(mode="json"),
        "updated_at": now,
    }

    if existing is None:
        record = InvestigationORM(
            id=result.id,
            incident_id=result.incident_id,
            created_at=result.created_at,
            **payload,
        )
        db.add(record)
    else:
        for key, value in payload.items():
            setattr(existing, key, value)
        record = existing

    inc_row = db.get(IncidentORM, result.incident_id)
    if inc_row is not None:
        inc_row.investigation_status = result.status
        inc_row.updated_at = now

    db.commit()
    db.refresh(record)
    return record


def to_investigation_result(record: InvestigationORM) -> InvestigationResult:
    """Convert an InvestigationORM row into the API InvestigationResult schema."""
    return InvestigationResult(
        id=record.id,
        incident_id=record.incident_id,
        status=record.status,  # type: ignore[arg-type]
        inference_mode=record.inference_mode,  # type: ignore[arg-type]
        model_name=record.model_name,
        summary=record.summary,
        root_cause_hypothesis=record.root_cause_hypothesis,
        probable_root_cause_service=record.probable_root_cause_service,
        supporting_evidence=[
            EvidenceItem.model_validate(item) for item in (record.supporting_evidence or [])
        ],
        limiting_evidence=list(record.limiting_evidence or []),
        affected_services=list(record.affected_services or []),
        service_roles=[
            ServiceRoleAssessment.model_validate(r) for r in (record.service_roles or [])
        ],
        contributing_factors=list(record.contributing_factors or []),
        blast_radius=BlastRadiusAssessment.model_validate(record.blast_radius),
        confidence=ConfidenceAssessment.model_validate(record.confidence),
        recommended_next_steps=list(record.recommended_next_steps or []),
        agent_trace=[
            LogicalAgentTrace.model_validate(t) for t in (record.agent_trace or [])
        ],
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def get_persisted_investigation(db: Session, incident_id: str) -> InvestigationResult | None:
    """Retrieve persisted investigation result by incident_id."""
    row = (
        db.execute(select(InvestigationORM).where(InvestigationORM.incident_id == incident_id))
        .scalar_one_or_none()
    )
    return to_investigation_result(row) if row is not None else None


def get_persisted_evidence_bundle(db: Session, incident_id: str) -> EvidenceBundle | None:
    """Retrieve the stored EvidenceBundle from a completed investigation if present."""
    row = (
        db.execute(select(InvestigationORM).where(InvestigationORM.incident_id == incident_id))
        .scalar_one_or_none()
    )
    if row is None or not row.evidence_bundle:
        return None
    return EvidenceBundle.model_validate(row.evidence_bundle)


def build_incident_timeline(
    db: Session, incident: DetectedIncident
) -> list[TimelineEntry]:
    """Combine incident monitoring events and SQLite audit records chronologically."""
    entries: list[TimelineEntry] = []

    for ev in incident.triggering_evidence:
        entries.append(
            TimelineEntry(
                timestamp=ev.timestamp,
                source="MONITORING_EVENT",
                event_type=ev.event_type,
                actor=ev.service_id,
                service_id=ev.service_id,
                tick=ev.tick,
                summary=f"[{ev.severity}] {ev.message}",
                details={
                    "event_id": ev.id,
                    "metric_name": ev.metric_name,
                    "metric_value": ev.metric_value,
                    "threshold_value": ev.threshold_value,
                },
            )
        )

    audit_rows = (
        db.execute(
            select(AuditLogORM)
            .where(AuditLogORM.incident_id == incident.id)
            .order_by(AuditLogORM.timestamp.asc())
        )
        .scalars()
        .all()
    )
    for row in audit_rows:
        entries.append(
            TimelineEntry(
                timestamp=row.timestamp,
                source="AUDIT_LOG",
                event_type=row.action,
                actor=f"{row.actor_type}:{row.actor_name}",
                service_id=row.details.get("root_cause_candidate")
                if isinstance(row.details, dict)
                else None,
                tick=row.details.get("tick") if isinstance(row.details, dict) else None,
                summary=f"{row.action} by {row.actor_name}",
                details=row.details if isinstance(row.details, dict) else {},
            )
        )

    entries.sort(key=lambda e: (e.timestamp.replace(tzinfo=None), 0 if e.source == "MONITORING_EVENT" else 1))
    return entries

