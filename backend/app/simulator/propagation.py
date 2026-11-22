"""Deterministic mathematical telemetry and dependency propagation equations."""

import math

from app.schemas.telemetry import ServiceHealthStatus, ServiceMetrics
from app.simulator.models import ActiveFault, ServiceBaseline, ServiceRuntimeState
from app.simulator.topology_graph import TopologyGraph


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def deterministic_wave(tick: int, service_index: int, amplitude: float = 0.025) -> float:
    """Return a tiny repeatable oscillation factor (1 +/- amplitude) with zero randomness."""
    return 1.0 + amplitude * math.sin(tick * 0.65 + service_index * 1.1)


def fault_pressure(tick: int, injected_tick: int, ramp_tau_ticks: float) -> float:
    """Compute bounded saturation ramp p(k) = 1 - exp(-k / tau) in [0, 1)."""
    elapsed_ticks = max(0, tick - injected_tick + 1)
    if elapsed_ticks == 0:
        return 0.0
    return 1.0 - math.exp(-elapsed_ticks / max(0.25, ramp_tau_ticks))


def classify_service_health(baseline: ServiceBaseline, metrics: ServiceMetrics) -> ServiceHealthStatus:
    """Deterministically classify service health against its SLO thresholds."""
    if (
        metrics.latency_ms >= baseline.slo_latency_ms * 3.0
        or metrics.error_rate >= max(0.10, baseline.slo_error_rate * 5.0)
        or metrics.saturation_pct >= 90.0
        or metrics.queue_depth >= 1000
    ):
        return "critical"

    if (
        metrics.latency_ms >= baseline.slo_latency_ms * 1.25
        or metrics.error_rate >= baseline.slo_error_rate * 2.0
        or metrics.saturation_pct >= 75.0
        or metrics.queue_depth >= 250
    ):
        return "degraded"

    return "healthy"


def propagate_tick(
    *,
    tick: int,
    tick_interval_seconds: float,
    topology: TopologyGraph,
    previous_states: dict[str, ServiceRuntimeState],
    active_faults: dict[str, ActiveFault],
) -> dict[str, ServiceRuntimeState]:
    """Compute the next tick's telemetry across all services using topological propagation.

    Evaluation proceeds bottom-up (dependencies before callers) so latency, error rates,
    saturation, and throughput degradation propagate mathematically through dependency
    weights. Queue accumulation on messaging-tier services follows conservation of flow
    between producer intake (checkout-api) and consumer drain (worker-fulfillment).
    """
    next_states: dict[str, ServiceRuntimeState] = {}
    service_indices = {svc.id: idx for idx, svc in enumerate(topology.services)}

    # Pre-compute worker effective drain capacity from previous tick so order-queue
    # backlog responds realistically to worker slowdown without cyclic graph evaluation.
    prev_checkout = previous_states["checkout-api"].metrics
    prev_worker = previous_states["worker-fulfillment"].metrics

    for service_id in topology.bottom_up_order():
        baseline = topology.get_service(service_id)
        prev_metrics = previous_states[service_id].metrics
        wave = deterministic_wave(tick, service_indices[service_id])

        # 1. Intrinsic service metrics (baseline + any direct fault injection)
        intrinsic_latency = baseline.baseline_latency_ms * wave
        intrinsic_error = baseline.baseline_error_rate * deterministic_wave(
            tick, service_indices[service_id] + 3, amplitude=0.05
        )
        intrinsic_cpu = baseline.baseline_cpu_pct * wave
        intrinsic_sat = baseline.baseline_saturation_pct * wave
        queue_depth = baseline.baseline_queue_depth

        fault = active_faults.get(service_id)
        if fault is not None:
            p = fault_pressure(tick, fault.injected_tick, fault.spec.ramp_tau_ticks)
            intrinsic_latency = baseline.baseline_latency_ms * (
                1.0
                + fault.spec.latency_linear_gain * p
                + fault.spec.latency_quadratic_gain * (p * p)
            )
            intrinsic_sat = baseline.baseline_saturation_pct + fault.spec.saturation_delta_pct * p
            intrinsic_cpu = baseline.baseline_cpu_pct + fault.spec.cpu_delta_pct * p
            intrinsic_error = baseline.baseline_error_rate + fault.spec.error_rate_delta * (p * p)

        # 2. Messaging-tier conservation of flow (order-queue backlog dynamics)
        if baseline.tier == "messaging":
            # Checkout intake + async retry pressure keeps enqueue rate elevated during timeouts
            checkout_base_rps = topology.get_service("checkout-api").baseline_throughput_rps
            enqueue_rps = max(
                prev_checkout.throughput_rps,
                checkout_base_rps * (1.0 - prev_checkout.error_rate * 0.15),
            )
            # Worker drain capacity drops sharply as DB lock latency and errors stall fulfillment
            worker_slowdown = max(
                0.08,
                1.0
                - prev_worker.error_rate * 1.8
                - min(0.82, max(0.0, prev_worker.latency_ms - 80.0) / 1100.0),
            )
            drain_capacity_rps = 210.0 * worker_slowdown
            net_delta = (enqueue_rps - drain_capacity_rps) * tick_interval_seconds
            if net_delta > 0:
                queue_depth = int(round(prev_metrics.queue_depth + net_delta))
            else:
                # Drain back smoothly toward healthy steady-state queue depth
                queue_depth = int(
                    round(max(baseline.baseline_queue_depth, prev_metrics.queue_depth + net_delta))
                )
            backlog_ratio = max(0.0, (queue_depth - baseline.baseline_queue_depth) / 1000.0)
            intrinsic_latency += backlog_ratio * 190.0
            intrinsic_sat += min(78.0, backlog_ratio * 42.0)
            intrinsic_cpu += min(52.0, backlog_ratio * 25.0)
            intrinsic_error += min(0.12, max(0.0, backlog_ratio - 0.5) * 0.03)

        # 3. Upstream dependency propagation (caller inherits weighted excess latency & failures)
        dep_latency_contrib = 0.0
        dep_error_contrib = 0.0
        dep_sat_contrib = 0.0

        for edge in topology.dependencies_of(service_id):
            dep_baseline = topology.get_service(edge.target_id)
            dep_metrics = next_states[edge.target_id].metrics

            excess_latency = max(0.0, dep_metrics.latency_ms - dep_baseline.baseline_latency_ms)
            slo_excess_ratio = max(
                0.0,
                (dep_metrics.latency_ms - dep_baseline.slo_latency_ms)
                / max(1.0, dep_baseline.slo_latency_ms * 7.0),
            )
            excess_error = max(0.0, dep_metrics.error_rate - dep_baseline.baseline_error_rate)

            dep_latency_contrib += edge.impact_weight * excess_latency * 0.82
            dep_error_contrib += edge.impact_weight * (excess_error * 0.95 + 0.28 * slo_excess_ratio)
            dep_sat_contrib += edge.impact_weight * min(58.0, (excess_latency / 32.0))

        # 4. Combine intrinsic + propagated signals with physical bounds
        latency_ms = round(_clamp(intrinsic_latency + dep_latency_contrib, 1.0, 8000.0), 2)
        error_rate = round(_clamp(intrinsic_error + dep_error_contrib, 0.0, 0.85), 4)
        saturation_pct = round(_clamp(intrinsic_sat + dep_sat_contrib, 0.0, 99.5), 2)
        cpu_pct = round(
            _clamp(intrinsic_cpu + dep_sat_contrib * 0.45 + dep_error_contrib * 30.0, 1.0, 99.0),
            2,
        )

        # Throughput drops under high error rates and severe latency backpressure
        excess_self_latency = max(0.0, latency_ms - baseline.baseline_latency_ms)
        throughput_factor = _clamp(
            1.0 - 0.55 * error_rate - 0.20 * min(1.0, excess_self_latency / 2500.0),
            0.15,
            1.05,
        )
        throughput_rps = round(baseline.baseline_throughput_rps * wave * throughput_factor, 2)

        metrics = ServiceMetrics(
            latency_ms=latency_ms,
            error_rate=error_rate,
            throughput_rps=throughput_rps,
            cpu_pct=cpu_pct,
            saturation_pct=saturation_pct,
            queue_depth=queue_depth,
        )

        new_state = ServiceRuntimeState(baseline=baseline)
        new_state.metrics = metrics
        new_state.status = classify_service_health(baseline, metrics)
        next_states[service_id] = new_state

    return next_states
