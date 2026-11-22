"""SQLite persistence and lifecycle orchestration for Phase 3 remediation plans."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.recovery import RecoveryAgent
from app.agents.trust import TrustAgent
from app.agents.verification import VerificationAgent
from app.db.models import IncidentORM, RemediationPlanORM
from app.recovery.executor import (
    ExecutionBlockedError,
    ExecutionStateError,
    SimulatedRecoveryExecutor,
)
from app.schemas.investigation import EvidenceBundle, InvestigationResult
from app.schemas.remediation import (
    ApprovalStatus,
    ExecutionRecord,
    PolicyEvaluationResult,
    RemediationPlan,
    VerificationResult,
)
from app.schemas.simulation import DetectedIncident
from app.services.audit_service import record_audit_event
from app.simulator.engine import SimulationEngine


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_remediation_plan(row: RemediationPlanORM) -> RemediationPlan:
    """Convert a RemediationPlanORM row into the API RemediationPlan schema."""
    return RemediationPlan(
        id=row.id,
        incident_id=row.incident_id,
        action_id=row.action_id,
        action_name=row.action_name,
        target_service=row.target_service,
        parameters=dict(row.parameters or {}),
        evidence_refs=list(row.evidence_refs or []),
        rationale=row.rationale,
        expected_effects=list(row.expected_effects or []),
        limitations=list(row.limitations or []),
        risks=list(row.risks or []),
        preconditions=list(row.preconditions or []),
        policy_decision=row.policy_decision,  # type: ignore[arg-type]
        policy_evaluation=PolicyEvaluationResult.model_validate(row.policy_evaluation),
        approval_status=row.approval_status,  # type: ignore[arg-type]
        approved_by=row.approved_by,
        approval_comment=row.approval_comment,
        approved_at=row.approved_at,
        execution_status=row.execution_status,  # type: ignore[arg-type]
        execution_record=(
            ExecutionRecord.model_validate(row.execution_record)
            if row.execution_record
            else None
        ),
        verification_status=row.verification_status,  # type: ignore[arg-type]
        verification_result=(
            VerificationResult.model_validate(row.verification_result)
            if row.verification_result
            else None
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _initial_approval_status(policy_decision: str) -> ApprovalStatus:
    if policy_decision == "AUTO_APPROVE":
        return "NOT_REQUIRED"
    if policy_decision == "DENY":
        return "DENIED"
    return "PENDING"


def _next_plan_id(db: Session) -> str:
    count = db.execute(select(func.count()).select_from(RemediationPlanORM)).scalar_one()
    return f"PLAN-{count + 1:04d}"


class RemediationService:
    """Coordinates RecoveryAgent, TrustAgent, Human Approval, Executor, and VerificationAgent."""

    def __init__(self) -> None:
        self._trust = TrustAgent()
        self._recovery = RecoveryAgent(trust_agent=self._trust)
        self._executor = SimulatedRecoveryExecutor()
        self._verifier = VerificationAgent()

    def list_plans(
        self, db: Session, incident_id: str | None = None
    ) -> list[RemediationPlan]:
        stmt = select(RemediationPlanORM).order_by(RemediationPlanORM.created_at.desc())
        if incident_id is not None:
            stmt = stmt.where(RemediationPlanORM.incident_id == incident_id)
        rows = db.execute(stmt).scalars().all()
        return [to_remediation_plan(r) for r in rows]

    def get_plan(self, db: Session, plan_id: str) -> RemediationPlan | None:
        row = db.get(RemediationPlanORM, plan_id)
        return to_remediation_plan(row) if row is not None else None

    def create_plan(
        self,
        *,
        db: Session,
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        evidence_bundle: EvidenceBundle | None,
        engine: SimulationEngine,
        override_action_id: str | None = None,
        override_target_service: str | None = None,
        override_parameters: dict[str, float | int | str | bool] | None = None,
    ) -> RemediationPlan:
        """Run RecoveryAgent + TrustAgent, persist plan, and write creation/policy audits."""
        draft = self._recovery.propose_plan(
            incident=incident,
            investigation=investigation,
            evidence_bundle=evidence_bundle,
            engine=engine,
            override_action_id=override_action_id,
            override_target_service=override_target_service,
            override_parameters=override_parameters,
        )

        now = _utc_now()
        plan_id = _next_plan_id(db)
        decision = draft.policy_evaluation.decision
        approval_status = _initial_approval_status(decision)

        row = RemediationPlanORM(
            id=plan_id,
            incident_id=incident.id,
            action_id=draft.action_id,
            action_name=draft.action_name,
            target_service=draft.target_service,
            parameters=draft.parameters,
            evidence_refs=draft.evidence_refs,
            rationale=draft.rationale,
            expected_effects=draft.expected_effects,
            limitations=draft.limitations,
            risks=draft.risks,
            preconditions=draft.preconditions,
            policy_decision=decision,
            policy_evaluation=draft.policy_evaluation.model_dump(mode="json"),
            approval_status=approval_status,
            execution_status="NOT_STARTED",
            verification_status="NOT_STARTED",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        record_audit_event(
            db,
            actor_type="AGENT",
            actor_name="RecoveryAgent",
            action="REMEDIATION_PLAN_CREATED",
            incident_id=incident.id,
            details={
                "plan_id": plan_id,
                "action_id": draft.action_id,
                "target_service": draft.target_service,
                "evidence_refs": draft.evidence_refs,
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )
        record_audit_event(
            db,
            actor_type="POLICY",
            actor_name="TrustAgent",
            action="POLICY_EVALUATED",
            incident_id=incident.id,
            details={
                "plan_id": plan_id,
                "action_id": draft.action_id,
                "policy_decision": decision,
                "approval_status": approval_status,
                "matched_rules": [r.rule_id for r in draft.policy_evaluation.matched_rules],
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )
        return to_remediation_plan(row)

    def evaluate_plan_policy(
        self,
        *,
        db: Session,
        plan_id: str,
        incident: DetectedIncident,
        investigation: InvestigationResult | None,
        engine: SimulationEngine,
    ) -> RemediationPlan:
        """Re-evaluate TrustAgent policy on an unexecuted plan."""
        row = db.get(RemediationPlanORM, plan_id)
        if row is None:
            raise KeyError(f"Remediation plan '{plan_id}' not found.")
        if row.execution_status != "NOT_STARTED":
            raise ExecutionStateError(
                f"Cannot re-evaluate policy after execution has started (status='{row.execution_status}')."
            )

        policy_eval = self._trust.evaluate(
            action_id=row.action_id,
            target_service=row.target_service,
            parameters=dict(row.parameters or {}),
            evidence_refs=list(row.evidence_refs or []),
            incident=incident,
            investigation=investigation,
            engine=engine,
        )
        row.policy_decision = policy_eval.decision
        row.policy_evaluation = policy_eval.model_dump(mode="json")
        if policy_eval.decision == "DENY":
            row.approval_status = "DENIED"
        elif policy_eval.decision == "AUTO_APPROVE" and row.approval_status == "PENDING":
            row.approval_status = "NOT_REQUIRED"
        elif policy_eval.decision == "REQUIRE_HUMAN_APPROVAL" and row.approval_status == "NOT_REQUIRED":
            row.approval_status = "PENDING"
        row.updated_at = _utc_now()
        db.commit()
        db.refresh(row)

        record_audit_event(
            db,
            actor_type="POLICY",
            actor_name="TrustAgent",
            action="POLICY_EVALUATED",
            incident_id=row.incident_id,
            details={
                "plan_id": row.id,
                "action_id": row.action_id,
                "policy_decision": row.policy_decision,
                "approval_status": row.approval_status,
                "matched_rules": [r.rule_id for r in policy_eval.matched_rules],
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )
        return to_remediation_plan(row)

    def approve_plan(
        self,
        *,
        db: Session,
        plan_id: str,
        actor: str,
        comment: str,
        engine: SimulationEngine,
    ) -> RemediationPlan:
        """Record human approval for a REQUIRE_HUMAN_APPROVAL plan in PENDING state."""
        row = db.get(RemediationPlanORM, plan_id)
        if row is None:
            raise KeyError(f"Remediation plan '{plan_id}' not found.")

        if row.policy_decision == "DENY":
            raise ExecutionBlockedError(
                f"Plan '{plan_id}' was DENIED by Trust Agent policy and cannot be approved."
            )
        if row.policy_decision != "REQUIRE_HUMAN_APPROVAL":
            raise ExecutionStateError(
                f"Plan '{plan_id}' does not require human approval (policy_decision='{row.policy_decision}')."
            )
        if row.approval_status != "PENDING":
            raise ExecutionStateError(
                f"Plan '{plan_id}' is not pending approval (current approval_status='{row.approval_status}')."
            )

        now = _utc_now()
        row.approval_status = "APPROVED"
        row.approved_by = actor
        row.approval_comment = comment
        row.approved_at = now
        row.updated_at = now
        db.commit()
        db.refresh(row)

        record_audit_event(
            db,
            actor_type="HUMAN",
            actor_name=actor,
            action="REMEDIATION_APPROVED",
            incident_id=row.incident_id,
            details={
                "plan_id": row.id,
                "action_id": row.action_id,
                "policy_decision": row.policy_decision,
                "approval_status": row.approval_status,
                "comment": comment,
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )
        return to_remediation_plan(row)

    def reject_plan(
        self,
        *,
        db: Session,
        plan_id: str,
        actor: str,
        comment: str,
        engine: SimulationEngine,
    ) -> RemediationPlan:
        """Record human rejection for a REQUIRE_HUMAN_APPROVAL plan in PENDING state."""
        row = db.get(RemediationPlanORM, plan_id)
        if row is None:
            raise KeyError(f"Remediation plan '{plan_id}' not found.")

        if row.policy_decision == "DENY":
            raise ExecutionBlockedError(
                f"Plan '{plan_id}' is already DENIED by Trust Agent policy."
            )
        if row.policy_decision != "REQUIRE_HUMAN_APPROVAL":
            raise ExecutionStateError(
                f"Plan '{plan_id}' does not require human approval (policy_decision='{row.policy_decision}')."
            )
        if row.approval_status != "PENDING":
            raise ExecutionStateError(
                f"Plan '{plan_id}' is not pending approval (current approval_status='{row.approval_status}')."
            )

        now = _utc_now()
        row.approval_status = "REJECTED"
        row.approved_by = actor
        row.approval_comment = comment
        row.approved_at = now
        row.updated_at = now
        db.commit()
        db.refresh(row)

        record_audit_event(
            db,
            actor_type="HUMAN",
            actor_name=actor,
            action="REMEDIATION_REJECTED",
            incident_id=row.incident_id,
            details={
                "plan_id": row.id,
                "action_id": row.action_id,
                "policy_decision": row.policy_decision,
                "approval_status": row.approval_status,
                "comment": comment,
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )
        return to_remediation_plan(row)

    def execute_plan(
        self,
        *,
        db: Session,
        plan_id: str,
        incident: DetectedIncident,
        engine: SimulationEngine,
    ) -> RemediationPlan:
        """Execute an approved/auto-approved allowlisted simulated plan and start verification."""
        row = db.get(RemediationPlanORM, plan_id)
        if row is None:
            raise KeyError(f"Remediation plan '{plan_id}' not found.")

        plan = to_remediation_plan(row)

        record_audit_event(
            db,
            actor_type="SYSTEM",
            actor_name="SimulatedRecoveryExecutor",
            action="REMEDIATION_EXECUTION_STARTED",
            incident_id=plan.incident_id,
            details={
                "plan_id": plan.id,
                "action_id": plan.action_id,
                "target_service": plan.target_service,
                "policy_decision": plan.policy_decision,
                "approval_status": plan.approval_status,
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )

        try:
            exec_record = self._executor.execute(plan=plan, incident=incident, engine=engine)
        except Exception as exc:
            record_audit_event(
                db,
                actor_type="SYSTEM",
                actor_name="SimulatedRecoveryExecutor",
                action="REMEDIATION_EXECUTION_FAILED",
                incident_id=plan.incident_id,
                details={
                    "plan_id": plan.id,
                    "action_id": plan.action_id,
                    "error": str(exc),
                    "tick": engine.tick,
                    "sim_time_s": engine.sim_time_s,
                },
            )
            raise

        now = _utc_now()
        row.execution_status = "COMPLETED"
        row.execution_record = exec_record.model_dump(mode="json")
        row.verification_status = "IN_PROGRESS"
        row.updated_at = now
        db.commit()
        db.refresh(row)

        record_audit_event(
            db,
            actor_type="SYSTEM",
            actor_name="SimulatedRecoveryExecutor",
            action="REMEDIATION_EXECUTION_COMPLETED",
            incident_id=plan.incident_id,
            details={
                "plan_id": plan.id,
                "execution_id": exec_record.execution_id,
                "action_id": plan.action_id,
                "execution_identifier": exec_record.execution_identifier,
                "applied_tick": exec_record.applied_tick,
                "sim_time_s": exec_record.applied_sim_time_s,
                "modeled_effect_summary": exec_record.modeled_effect_summary,
            },
        )
        record_audit_event(
            db,
            actor_type="AGENT",
            actor_name="VerificationAgent",
            action="VERIFICATION_STARTED",
            incident_id=plan.incident_id,
            details={
                "plan_id": plan.id,
                "action_id": plan.action_id,
                "applied_tick": exec_record.applied_tick,
                "tick": engine.tick,
                "sim_time_s": engine.sim_time_s,
            },
        )
        return to_remediation_plan(row)

    def verify_plan(
        self,
        *,
        db: Session,
        plan_id: str,
        incident: DetectedIncident,
        engine: SimulationEngine,
    ) -> VerificationResult:
        """Evaluate post-execution telemetry; resolve incident ONLY when VERIFIED."""
        row = db.get(RemediationPlanORM, plan_id)
        if row is None:
            raise KeyError(f"Remediation plan '{plan_id}' not found.")

        plan = to_remediation_plan(row)
        if plan.execution_record is None:
            raise ExecutionStateError(
                f"Plan '{plan_id}' has not been executed yet; verification is unavailable."
            )

        # Return terminal verification result idempotently without duplicate audits
        if row.verification_status in ("VERIFIED", "FAILED") and row.verification_result:
            return VerificationResult.model_validate(row.verification_result)

        result = self._verifier.evaluate(
            plan=plan,
            affected_services=incident.affected_services,
            engine=engine,
        )

        now = _utc_now()
        previous_status = row.verification_status
        row.verification_status = result.status
        row.verification_result = result.model_dump(mode="json")
        row.updated_at = now

        if result.status == "VERIFIED" and previous_status != "VERIFIED":
            # Transition persisted incident and in-memory detector state to RESOLVED
            inc_row = db.get(IncidentORM, row.incident_id)
            if inc_row is not None:
                inc_row.status = "RESOLVED"
                inc_row.updated_tick = engine.tick
                inc_row.updated_at = now
            live_inc = engine.detector.get_incident(row.incident_id)
            if live_inc is not None and live_inc.status != "RESOLVED":
                engine.detector._incidents[row.incident_id] = live_inc.model_copy(
                    update={"status": "RESOLVED", "updated_tick": engine.tick, "updated_at": now}
                )
            db.commit()

            record_audit_event(
                db,
                actor_type="AGENT",
                actor_name="VerificationAgent",
                action="VERIFICATION_COMPLETED",
                incident_id=row.incident_id,
                details={
                    "plan_id": row.id,
                    "action_id": row.action_id,
                    "verification_status": "VERIFIED",
                    "consecutive_healthy_ticks": result.consecutive_healthy_ticks,
                    "resilience_score": result.resilience_score,
                    "tick": engine.tick,
                    "sim_time_s": engine.sim_time_s,
                },
            )
            record_audit_event(
                db,
                actor_type="SYSTEM",
                actor_name="RemediationService",
                action="INCIDENT_RESOLVED",
                incident_id=row.incident_id,
                details={
                    "plan_id": row.id,
                    "action_id": row.action_id,
                    "resilience_score": result.resilience_score,
                    "tick": engine.tick,
                    "sim_time_s": engine.sim_time_s,
                },
            )
        elif result.status == "FAILED" and previous_status != "FAILED":
            db.commit()
            record_audit_event(
                db,
                actor_type="AGENT",
                actor_name="VerificationAgent",
                action="VERIFICATION_FAILED",
                incident_id=row.incident_id,
                details={
                    "plan_id": row.id,
                    "action_id": row.action_id,
                    "verification_status": "FAILED",
                    "elapsed_ticks": result.elapsed_ticks_since_execution,
                    "summary": result.summary,
                    "tick": engine.tick,
                    "sim_time_s": engine.sim_time_s,
                },
            )
        else:
            db.commit()

        return result

