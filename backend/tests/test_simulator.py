"""Deterministic unit tests for the NEXUS Phase 1 infrastructure simulator."""

from app.simulator.engine import SimulationEngine


def test_initial_healthy_state_and_topology() -> None:
    """Engine initializes with all 7 approved services healthy and 8 dependency edges."""
    engine = SimulationEngine()
    topo = engine.get_topology_snapshot()
    status = engine.get_status(running=False)

    assert len(topo.nodes) == 7
    assert len(topo.edges) == 8
    node_ids = {n.id for n in topo.nodes}
    assert node_ids == {
        "api-gateway",
        "auth-service",
        "checkout-api",
        "payment-service",
        "order-queue",
        "worker-fulfillment",
        "postgres-primary",
    }
    assert status.tick == 0
    assert status.healthy_services == 7
    assert status.degraded_services == 0
    assert status.critical_services == 0
    assert status.active_incidents_count == 0
    assert status.resilience_score >= 95.0


def test_healthy_tick_advancement_changes_telemetry_without_incidents() -> None:
    """Advancing ticks in healthy state updates telemetry subtly without false incidents."""
    engine = SimulationEngine()
    t0 = {s.service_id: s.metrics.latency_ms for s in engine.get_latest_telemetry()}

    events, new_incidents = engine.step(ticks=3)
    t3 = {s.service_id: s.metrics.latency_ms for s in engine.get_latest_telemetry()}

    assert engine.tick == 3
    assert engine.sim_time_s == 6.0
    assert events == []
    assert new_incidents == []
    assert any(t0[sid] != t3[sid] for sid in t0)
    assert engine.get_status(running=False).healthy_services == 7


def test_db_latency_cascade_propagation_and_queue_accumulation() -> None:
    """Injecting db_latency_cascade degrades postgres-primary and propagates through dependencies."""
    engine = SimulationEngine()
    baseline_by_svc = {s.service_id: s.metrics for s in engine.get_latest_telemetry()}

    engine.inject_scenario("db_latency_cascade")
    engine.step(ticks=6)

    topo = engine.get_topology_snapshot()
    nodes = {n.id: n for n in topo.nodes}

    # 1. Database degrades sharply
    pg = nodes["postgres-primary"]
    assert pg.status == "critical"
    assert pg.metrics.latency_ms > baseline_by_svc["postgres-primary"].latency_ms * 20
    assert pg.metrics.saturation_pct > 85.0
    assert pg.metrics.cpu_pct > 80.0

    # 2. Dependent services degrade via topology propagation
    assert nodes["payment-service"].status in ("degraded", "critical")
    assert nodes["checkout-api"].status in ("degraded", "critical")
    assert nodes["worker-fulfillment"].status in ("degraded", "critical")
    assert nodes["api-gateway"].status in ("degraded", "critical")
    assert nodes["payment-service"].metrics.latency_ms > baseline_by_svc["payment-service"].latency_ms * 5
    assert nodes["checkout-api"].metrics.error_rate > 0.05

    # 3. Order queue accumulates backlog as worker-fulfillment slows down
    assert nodes["order-queue"].metrics.queue_depth > 250
    assert nodes["order-queue"].status in ("degraded", "critical")

    # 4. Non-dependent auth-service remains healthy (proves topology-aware propagation)
    assert nodes["auth-service"].status == "healthy"


def test_deterministic_incident_detection_and_root_cause_candidate() -> None:
    """Cascading failure triggers correlated CRITICAL incident rooted at postgres-primary."""
    engine = SimulationEngine()
    engine.inject_scenario("db_latency_cascade")
    engine.step(ticks=5)

    incidents = engine.detector.list_incidents()
    assert len(incidents) == 1
    inc = incidents[0]

    assert inc.id == "INC-0001"
    assert inc.scenario_id == "db_latency_cascade"
    assert inc.severity == "CRITICAL"
    assert inc.status in ("DETECTED", "ACTIVE")
    assert inc.root_cause_candidate == "postgres-primary"
    assert "postgres-primary" in inc.affected_services
    assert "payment-service" in inc.affected_services
    assert "checkout-api" in inc.affected_services
    assert "auth-service" not in inc.affected_services
    assert len(inc.triggering_evidence) >= 3
    assert inc.root_cause_rationale is not None


def test_reset_restores_healthy_baseline() -> None:
    """Resetting the simulator restores all services to healthy and clears active incidents."""
    engine = SimulationEngine()
    engine.inject_scenario("db_latency_cascade")
    engine.step(ticks=6)
    assert engine.get_status(running=False).critical_services >= 1
    assert len(engine.detector.list_incidents()) == 1

    engine.reset(clear_incidents=True)
    status = engine.get_status(running=False)
    assert status.tick == 0
    assert status.active_scenario is None
    assert status.healthy_services == 7
    assert status.degraded_services == 0
    assert status.critical_services == 0
    assert status.active_incidents_count == 0
    assert status.resilience_score >= 95.0
    assert engine.detector.list_incidents() == []


def test_simulation_is_strictly_repeatable_and_deterministic() -> None:
    """Two independent runs of the same scenario produce identical telemetry and incidents."""
    engine_a = SimulationEngine()
    engine_b = SimulationEngine()

    engine_a.inject_scenario("db_latency_cascade")
    engine_b.inject_scenario("db_latency_cascade")

    engine_a.step(ticks=6)
    engine_b.step(ticks=6)

    topo_a = engine_a.get_topology_snapshot().model_dump(mode="json")
    topo_b = engine_b.get_topology_snapshot().model_dump(mode="json")
    inc_a = [i.model_dump(mode="json") for i in engine_a.detector.list_incidents()]
    inc_b = [i.model_dump(mode="json") for i in engine_b.detector.list_incidents()]

    assert topo_a == topo_b
    assert inc_a == inc_b

