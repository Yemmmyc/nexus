"""Controlled simulated remediation executor enforcing allowlist, policy, and approval gates."""

from datetime import datetime, timezone

from app.recovery.catalog import get_catalog_action, validate_action_parameters
from app.schemas.remediation import ExecutionRecord, RemediationPlan
from app.schemas.simulation import DetectedIncident
from app.simulator.engine import SimulationEngine
from app.simulator.models import ActiveMitigation


class ExecutionBlockedError(PermissionError):
    """Raised when policy, approval, or allowlist validation blocks execution."""


class ExecutionStateError(ValueError):
    """Raised when plan state prevents execution (e.g., duplicate execution)."""


class SimulatedRecoveryExecutor:
    """Executes ONLY allowlisted, policy-permitted, approved simulated mitigations."""

    def execute(
        self,
        *,
        plan: RemediationPlan,
        incident: DetectedIncident,
        engine: SimulationEngine,
    ) -> ExecutionRecord:
        """Validate all safety gates and register the modeled mitigation in SimulationEngine."""
        # 1. Prevent duplicate execution
        if plan.execution_status != "NOT_STARTED":
            raise ExecutionStateError(
                f"Plan '{plan.id}' has already been executed or is in state '{plan.execution_status}'."
            )

        # 2. Enforce Trust Agent policy & approval gates (defense in depth)
        if plan.policy_decision == "DENY":
            raise ExecutionBlockedError(
                f"Execution blocked: plan '{plan.id}' was DENIED by Trust Agent policy."
            )
        if plan.policy_decision == "REQUIRE_HUMAN_APPROVAL" and plan.approval_status != "APPROVED":
            raise ExecutionBlockedError(
                f"Execution blocked: plan '{plan.id}' requires human approval "
                f"(current approval_status='{plan.approval_status}')."
            )
        if plan.policy_decision not in ("AUTO_APPROVE", "REQUIRE_HUMAN_APPROVAL"):
            raise ExecutionBlockedError(f"Unsupported policy decision '{plan.policy_decision}'.")

        # 3. Validate action allowlist, target, and parameter bounds
        action_def = get_catalog_action(plan.action_id)
        if action_def is None:
            raise ExecutionBlockedError(
                f"Execution blocked: action '{plan.action_id}' is not in the static allowlist."
            )
        if plan.target_service not in action_def.allowed_targets:
            raise ExecutionBlockedError(
                f"Execution blocked: target '{plan.target_service}' is invalid for '{plan.action_id}'."
            )
        param_errors = validate_action_parameters(action_def, plan.parameters)
        if param_errors:
            raise ExecutionBlockedError(f"Execution blocked: {'; '.join(param_errors)}")

        # 4. Validate incident precondition
        if incident.status == "RESOLVED":
            raise ExecutionStateError(
                f"Precondition failed: incident '{incident.id}' is already RESOLVED."
            )

        started_at = datetime.now(timezone.utc)
        applied_tick = engine.tick + 1
        mitigation, effect_summary = self._build_mitigation(
            action_id=plan.action_id,
            target_service=plan.target_service,
            parameters=plan.parameters,
            applied_tick=applied_tick,
        )

        # Apply modeled mitigation to simulator state (takes effect deterministically across ticks)
        engine.apply_mitigation(mitigation)
        completed_at = datetime.now(timezone.utc)

        return ExecutionRecord(
            execution_id=f"EXEC-{plan.id}",
            plan_id=plan.id,
            incident_id=plan.incident_id,
            action_id=plan.action_id,
            execution_identifier=action_def.execution_identifier,
            target_service=plan.target_service,
            parameters=dict(plan.parameters),
            status="COMPLETED",
            applied_tick=applied_tick,
            applied_sim_time_s=round(applied_tick * engine.tick_interval_seconds, 2),
            modeled_effect_summary=effect_summary,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _build_mitigation(
        *,
        action_id: str,
        target_service: str,
        parameters: dict[str, float | int | str | bool],
        applied_tick: int,
    ) -> tuple[ActiveMitigation, str]:
        if action_id == "expand_db_connection_pool":
            multiplier = float(parameters.get("pool_multiplier", 2.0))
            # Relief scales smoothly with multiplier (2.0x -> 0.94 relief)
            relief = min(0.96, 0.70 + (multiplier - 1.2) * 0.30)
            mit = ActiveMitigation(
                action_id=action_id,
                target_service_id=target_service,
                applied_tick=applied_tick,
                ramp_tau_ticks=1.4,
                fault_relief_factor=round(relief, 3),
            )
            summary = (
                f"Applied simulated DB connection pool expansion ({multiplier}x, "
                f"fault_relief_factor={mit.fault_relief_factor}, tau={mit.ramp_tau_ticks} ticks) "
                f"on '{target_service}'."
            )
            return mit, summary

        if action_id == "enable_circuit_breaker":
            threshold = float(parameters.get("error_threshold_pct", 25.0))
            iso = max(0.35, min(0.75, 0.80 - threshold / 120.0))
            mit = ActiveMitigation(
                action_id=action_id,
                target_service_id=target_service,
                applied_tick=applied_tick,
                ramp_tau_ticks=1.0,
                edge_isolation_factor=round(iso, 3),
            )
            summary = (
                f"Applied simulated circuit breaker (error_threshold={threshold}%, "
                f"edge_isolation_factor={mit.edge_isolation_factor}) on '{target_service}'."
            )
            return mit, summary

        if action_id == "scale_queue_consumers":
            multiplier = float(parameters.get("consumer_multiplier", 2.4))
            mit = ActiveMitigation(
                action_id=action_id,
                target_service_id=target_service,
                applied_tick=applied_tick,
                ramp_tau_ticks=1.2,
                drain_boost_multiplier=multiplier,
            )
            summary = (
                f"Applied simulated queue consumer scaling ({multiplier}x drain capacity boost) "
                f"on '{target_service}'."
            )
            return mit, summary

        raise ExecutionBlockedError(f"No simulated handler registered for action '{action_id}'.")

