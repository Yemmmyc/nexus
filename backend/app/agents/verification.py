"""Verification Agent: evaluates multi-tick post-remediation telemetry against SLO thresholds."""

from datetime import datetime, timezone

from app.schemas.remediation import (
    RemediationPlan,
    ServiceVerificationCheck,
    VerificationResult,
    VerificationStatus,
)
from app.simulator.engine import SimulationEngine


class VerificationAgent:
    """Evaluates whether simulated remediation restored healthy SLO state across consecutive ticks.

    Verification thresholds:
    - Target service and critical downstream services must be classified 'healthy'
      (latency < 1.25 * slo_latency_ms, error_rate < 2.0 * slo_error_rate, saturation < 75%).
    - order-queue depth must be < 250 pending messages.
    - Conditions must hold for `required_consecutive_healthy_ticks` consecutive ticks
      (default: 2) within `max_verification_ticks` (default: 10) after execution.
    """

    REQUIRED_CONSECUTIVE_HEALTHY_TICKS = 2
    MAX_VERIFICATION_TICKS = 10
    QUEUE_HEALTHY_THRESHOLD = 250

    def evaluate(
        self,
        *,
        plan: RemediationPlan,
        affected_services: list[str],
        engine: SimulationEngine,
    ) -> VerificationResult:
        """Evaluate current simulated telemetry and multi-tick stability for a remediation plan."""
        if plan.execution_record is None:
            raise ValueError(f"Plan '{plan.id}' has not been executed yet.")

        applied_tick = plan.execution_record.applied_tick
        current_tick = engine.tick
        elapsed = max(0, current_tick - applied_tick + 1) if current_tick >= applied_tick else 0

        topo = engine.get_topology_snapshot()
        nodes_by_id = {n.id: n for n in topo.nodes}

        # Scope checks to target service + all affected services + critical checkout path
        check_service_ids = sorted(
            set(affected_services) | {plan.target_service, "order-queue"}
        )

        checks: list[ServiceVerificationCheck] = []
        for sid in check_service_ids:
            node = nodes_by_id[sid]
            m = node.metrics
            queue_ok = m.queue_depth < self.QUEUE_HEALTHY_THRESHOLD if sid == "order-queue" else True
            passed = node.status == "healthy" and queue_ok
            note = (
                "Within SLO thresholds."
                if passed
                else (
                    f"status={node.status}, latency={m.latency_ms:.1f}ms (SLO {node.slo_latency_ms:.0f}ms), "
                    f"error={m.error_rate * 100:.1f}%, sat={m.saturation_pct:.1f}%, q={m.queue_depth}"
                )
            )
            checks.append(
                ServiceVerificationCheck(
                    service_id=sid,
                    status=node.status,
                    latency_ms=m.latency_ms,
                    slo_latency_ms=node.slo_latency_ms,
                    error_rate=m.error_rate,
                    slo_error_rate=node.slo_error_rate,
                    saturation_pct=m.saturation_pct,
                    queue_depth=m.queue_depth,
                    passed=passed,
                    note=note,
                )
            )

        # Count consecutive healthy ticks directly from recorded telemetry history since applied_tick
        consecutive_healthy = self._count_consecutive_healthy_ticks(
            service_ids=check_service_ids,
            applied_tick=applied_tick,
            engine=engine,
        )

        status: VerificationStatus
        if consecutive_healthy >= self.REQUIRED_CONSECUTIVE_HEALTHY_TICKS:
            status = "VERIFIED"
            summary = (
                f"Recovery verified: all {len(check_service_ids)} monitored services met SLO "
                f"thresholds across {consecutive_healthy} consecutive ticks "
                f"(resilience score {engine.calculate_resilience_score():.1f})."
            )
        elif elapsed >= self.MAX_VERIFICATION_TICKS:
            failing = [c.service_id for c in checks if not c.passed]
            status = "FAILED"
            summary = (
                f"Verification failed after {elapsed} ticks since execution "
                f"(max window {self.MAX_VERIFICATION_TICKS} ticks). "
                f"Unrecovered service(s): {', '.join(failing) or 'stability window not met'}."
            )
        else:
            failing = [c.service_id for c in checks if not c.passed]
            status = "IN_PROGRESS"
            if failing:
                summary = (
                    f"Verification in progress (tick {current_tick}, elapsed {elapsed}/{self.MAX_VERIFICATION_TICKS}): "
                    f"waiting for {', '.join(failing)} to return within SLO."
                )
            else:
                summary = (
                    f"Verification in progress (tick {current_tick}): all services healthy for "
                    f"{consecutive_healthy}/{self.REQUIRED_CONSECUTIVE_HEALTHY_TICKS} required consecutive ticks."
                )

        return VerificationResult(
            plan_id=plan.id,
            incident_id=plan.incident_id,
            status=status,
            evaluated_tick=current_tick,
            evaluated_sim_time_s=engine.sim_time_s,
            applied_tick=applied_tick,
            elapsed_ticks_since_execution=elapsed,
            consecutive_healthy_ticks=consecutive_healthy,
            required_consecutive_healthy_ticks=self.REQUIRED_CONSECUTIVE_HEALTHY_TICKS,
            max_verification_ticks=self.MAX_VERIFICATION_TICKS,
            resilience_score=engine.calculate_resilience_score(),
            checks=checks,
            summary=summary,
            evaluated_at=datetime.now(timezone.utc),
        )

    def _count_consecutive_healthy_ticks(
        self,
        *,
        service_ids: list[str],
        applied_tick: int,
        engine: SimulationEngine,
    ) -> int:
        """Inspect telemetry history backwards from current tick to count consecutive healthy ticks."""
        if engine.tick < applied_tick:
            return 0

        # Build tick -> {service_id: sample} lookup for recent post-execution ticks
        by_tick: dict[int, dict[str, tuple[str, int]]] = {}
        for sid in service_ids:
            for sample in engine.get_telemetry_history(service_id=sid, limit=30):
                if sample.tick >= applied_tick:
                    by_tick.setdefault(sample.tick, {})[sid] = (
                        sample.status,
                        sample.metrics.queue_depth,
                    )

        consecutive = 0
        for t in range(engine.tick, applied_tick - 1, -1):
            tick_map = by_tick.get(t)
            if not tick_map or len(tick_map) < len(service_ids):
                break
            all_ok = all(
                status == "healthy"
                and (q_depth < self.QUEUE_HEALTHY_THRESHOLD if sid == "order-queue" else True)
                for sid, (status, q_depth) in tick_map.items()
            )
            if all_ok:
                consecutive += 1
            else:
                break
        return consecutive

