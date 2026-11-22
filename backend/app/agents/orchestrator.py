"""Logical agent orchestrator for Phase 2 incident intelligence."""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.investigator import InvestigatorAgent
from app.agents.llm_adapter import OptionalLLMAdapter
from app.agents.observer import ObserverAgent
from app.agents.risk_analyst import RiskAnalystAgent
from app.config import Settings
from app.db.models import IncidentORM
from app.schemas.investigation import (
    EvidenceBundle,
    InvestigationResult,
    LogicalAgentTrace,
)
from app.schemas.simulation import DetectedIncident
from app.services.audit_service import record_audit_event
from app.services.incident_repository import save_investigation, upsert_incident
from app.simulator.engine import SimulationEngine


class InvestigationOrchestrator:
    """Coordinates Observer -> Investigator -> Risk Analyst with full SQLite auditability."""

    def __init__(
        self,
        settings: Settings,
        llm_adapter: OptionalLLMAdapter | None = None,
    ) -> None:
        self._observer = ObserverAgent()
        self._investigator = InvestigatorAgent(settings=settings, llm_adapter=llm_adapter)
        self._risk_analyst = RiskAnalystAgent()

    def collect_evidence(
        self, incident: DetectedIncident, engine: SimulationEngine
    ) -> EvidenceBundle:
        """Run Observer agent read-only to assemble current incident evidence."""
        return self._observer.collect(incident, engine)

    def run_investigation(
        self,
        *,
        incident: DetectedIncident,
        engine: SimulationEngine,
        db: Session,
    ) -> InvestigationResult:
        """Execute the 3-role logical investigation pipeline and persist findings + audit logs."""
        upsert_incident(db, incident, tick_interval_seconds=engine.tick_interval_seconds)

        inc_row = db.get(IncidentORM, incident.id)
        if inc_row is not None:
            inc_row.investigation_status = "RUNNING"
            db.commit()

        record_audit_event(
            db,
            actor_type="AGENT",
            actor_name="InvestigationOrchestrator",
            action="INVESTIGATION_STARTED",
            incident_id=incident.id,
            details={"tick": engine.tick, "affected_services": incident.affected_services},
        )

        traces: list[LogicalAgentTrace] = []
        try:
            # 1. Observer Agent
            t0 = time.perf_counter()
            bundle = self._observer.collect(incident, engine)
            obs_ms = int((time.perf_counter() - t0) * 1000)
            traces.append(
                LogicalAgentTrace(
                    agent_role="Observer",
                    status="COMPLETED",
                    inference_mode="DETERMINISTIC",
                    duration_ms=obs_ms,
                    summary=(
                        f"Collected {len(bundle.items)} traceable evidence items across "
                        f"{len(bundle.affected_services)} affected services."
                    ),
                )
            )

            # 2. Investigator Agent
            t1 = time.perf_counter()
            inv_out = self._investigator.investigate(bundle, engine.topology)
            inv_ms = int((time.perf_counter() - t1) * 1000)
            traces.append(
                LogicalAgentTrace(
                    agent_role="Investigator",
                    status="COMPLETED",
                    inference_mode=inv_out.inference_mode,
                    duration_ms=inv_ms,
                    summary=(
                        f"Identified '{inv_out.probable_root_cause_service}' as probable root cause "
                        f"(confidence {inv_out.confidence.score:.2f}, {inv_out.confidence.level})."
                    ),
                )
            )

            # 3. Risk Analyst Agent
            t2 = time.perf_counter()
            blast_radius = self._risk_analyst.assess(bundle, engine.topology)
            risk_ms = int((time.perf_counter() - t2) * 1000)
            traces.append(
                LogicalAgentTrace(
                    agent_role="Risk Analyst",
                    status="COMPLETED",
                    inference_mode="DETERMINISTIC",
                    duration_ms=risk_ms,
                    summary=(
                        f"Assessed risk score {blast_radius.risk_score}/100 ({blast_radius.risk_level}); "
                        f"{blast_radius.impacted_service_count}/{blast_radius.total_service_count} services impacted."
                    ),
                )
            )

            now = datetime.now(timezone.utc)
            result = InvestigationResult(
                id=f"INV-{incident.id}",
                incident_id=incident.id,
                status="COMPLETED",
                inference_mode=inv_out.inference_mode,
                model_name=inv_out.model_name,
                summary=inv_out.summary,
                root_cause_hypothesis=inv_out.root_cause_hypothesis,
                probable_root_cause_service=inv_out.probable_root_cause_service,
                supporting_evidence=inv_out.supporting_evidence,
                limiting_evidence=inv_out.limiting_evidence,
                affected_services=bundle.affected_services,
                service_roles=inv_out.service_roles,
                contributing_factors=inv_out.contributing_factors,
                blast_radius=blast_radius,
                confidence=inv_out.confidence,
                recommended_next_steps=inv_out.recommended_next_steps,
                agent_trace=traces,
                created_at=now,
                updated_at=now,
            )

            save_investigation(db, result, bundle)

            record_audit_event(
                db,
                actor_type="AGENT",
                actor_name="InvestigationOrchestrator",
                action="INVESTIGATION_COMPLETED",
                incident_id=incident.id,
                details={
                    "investigation_id": result.id,
                    "inference_mode": result.inference_mode,
                    "probable_root_cause_service": result.probable_root_cause_service,
                    "confidence_score": result.confidence.score,
                    "risk_score": result.blast_radius.risk_score,
                    "evidence_count": len(result.supporting_evidence),
                },
            )
            record_audit_event(
                db,
                actor_type="SYSTEM",
                actor_name="IncidentRepository",
                action="INCIDENT_UPDATED",
                incident_id=incident.id,
                details={
                    "investigation_status": "COMPLETED",
                    "probable_root_cause_service": result.probable_root_cause_service,
                },
            )
            return result

        except Exception as exc:
            inc_row = db.get(IncidentORM, incident.id)
            if inc_row is not None:
                inc_row.investigation_status = "FAILED"
                db.commit()
            record_audit_event(
                db,
                actor_type="AGENT",
                actor_name="InvestigationOrchestrator",
                action="INVESTIGATION_FAILED",
                incident_id=incident.id,
                details={"error": str(exc)},
            )
            raise

