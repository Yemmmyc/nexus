"""Phase 1.1 focused verification tests for deterministic cascade, lifecycle, and audit guarantees."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import build_engine, get_db, init_db
from app.db.models import AuditLogORM
from app.db.seed import seed_initial_data
from app.main import create_app
from app.services.simulation_service import SimulationController
from app.simulator.engine import SimulationEngine
from app.simulator.propagation import fault_pressure


def test_fault_propagation_matches_implemented_model() -> None:
    """Verify postgres-primary fault curve, topological propagation, and auth-service isolation."""
    engine = SimulationEngine()
    spec = engine.scenarios.get_scenario("db_latency_cascade")
    fault = spec.faults[0]
    pg_base = engine.topology.get_service("postgres-primary")

    engine.inject_scenario("db_latency_cascade")

    prev_pg_latency = pg_base.baseline_latency_ms
    prev_pg_sat = pg_base.baseline_saturation_pct
    for tick in range(1, 7):
        engine.step(ticks=1)
        topo = engine.get_topology_snapshot()
        nodes = {n.id: n for n in topo.nodes}
        pg = nodes["postgres-primary"]

        # Exact mathematical expectation from propagation.py
        p = fault_pressure(tick=tick, injected_tick=1, ramp_tau_ticks=fault.ramp_tau_ticks)
        expected_lat = round(
            min(
                8000.0,
                pg_base.baseline_latency_ms
                * (1.0 + fault.latency_linear_gain * p + fault.latency_quadratic_gain * p * p),
            ),
            2,
        )
        expected_sat = round(min(99.5, pg_base.baseline_saturation_pct + fault.saturation_delta_pct * p), 2)
        expected_err = round(min(0.85, pg_base.baseline_error_rate + fault.error_rate_delta * p * p), 4)

        assert pg.metrics.latency_ms == expected_lat
        assert pg.metrics.saturation_pct == expected_sat
        assert pg.metrics.error_rate == expected_err
        assert pg.metrics.latency_ms > prev_pg_latency
        assert pg.metrics.saturation_pct > prev_pg_sat

        # Non-dependent service remains unaffected on every tick
        assert nodes["auth-service"].status == "healthy"
        prev_pg_latency = pg.metrics.latency_ms
        prev_pg_sat = pg.metrics.saturation_pct


def test_queue_conservation_of_flow_across_ticks() -> None:
    """Verify order-queue depth progression matches the conservation-of-flow equation each tick."""
    engine = SimulationEngine()
    engine.inject_scenario("db_latency_cascade")

    checkout_base_rps = engine.topology.get_service("checkout-api").baseline_throughput_rps
    queue_base = engine.topology.get_service("order-queue").baseline_queue_depth
    dt = engine.tick_interval_seconds

    prev_nodes = {n.id: n for n in engine.get_topology_snapshot().nodes}
    depths: list[int] = [prev_nodes["order-queue"].metrics.queue_depth]

    for _ in range(6):
        prev_checkout = prev_nodes["checkout-api"].metrics
        prev_worker = prev_nodes["worker-fulfillment"].metrics
        prev_q_depth = prev_nodes["order-queue"].metrics.queue_depth

        enqueue_rps = max(
            prev_checkout.throughput_rps,
            checkout_base_rps * (1.0 - prev_checkout.error_rate * 0.15),
        )
        worker_slowdown = max(
            0.08,
            1.0
            - prev_worker.error_rate * 1.8
            - min(0.82, max(0.0, prev_worker.latency_ms - 80.0) / 1100.0),
        )
        drain_capacity_rps = 210.0 * worker_slowdown
        net_delta = (enqueue_rps - drain_capacity_rps) * dt
        expected_depth = (
            int(round(prev_q_depth + net_delta))
            if net_delta > 0
            else int(round(max(queue_base, prev_q_depth + net_delta)))
        )

        engine.step(ticks=1)
        curr_nodes = {n.id: n for n in engine.get_topology_snapshot().nodes}
        observed_depth = curr_nodes["order-queue"].metrics.queue_depth
        assert observed_depth == expected_depth
        depths.append(observed_depth)
        prev_nodes = curr_nodes

    # Queue depth strictly accumulates once worker degradation sets in
    assert depths[-1] > depths[0]
    assert depths[-1] > 250


def test_deterministic_replay_full_state_comparison() -> None:
    """Verify two independent runs yield identical telemetry, events, incidents, and scores."""
    def run_once() -> dict:
        eng = SimulationEngine()
        eng.inject_scenario("db_latency_cascade")
        tick_events = []
        resilience_series = []
        for _ in range(6):
            evs, _ = eng.step(ticks=1)
            tick_events.append([e.model_dump(mode="json") for e in evs])
            resilience_series.append(eng.calculate_resilience_score())
        return {
            "topology": eng.get_topology_snapshot().model_dump(mode="json"),
            "history": [s.model_dump(mode="json") for s in eng.get_telemetry_history(limit=20)],
            "events": tick_events,
            "incidents": [i.model_dump(mode="json") for i in eng.detector.list_incidents()],
            "resilience": resilience_series,
        }

    run_a = run_once()
    run_b = run_once()
    assert run_a == run_b


def test_start_stop_lifecycle_idempotency_and_reset_while_running() -> None:
    """Verify start/stop idempotency, single background task, no ticks after stop, and reset while running."""

    async def _run() -> None:
        controller = SimulationController(tick_interval_seconds=0.05)

        # Start
        s1 = await controller.start()
        assert s1.running is True
        first_task = controller._task
        assert first_task is not None

        # Repeated start must not spawn a second background loop
        s2 = await controller.start()
        assert s2.running is True
        assert controller._task is first_task

        # Wait briefly for at least 1 tick
        await asyncio.sleep(0.14)
        assert controller.engine.tick >= 1

        # Stop
        s3 = await controller.stop()
        assert s3.running is False
        assert controller._task is None
        tick_at_stop = controller.engine.tick

        # Repeated stop is safe and idempotent
        s4 = await controller.stop()
        assert s4.running is False

        # Ticks must not continue after stopping
        await asyncio.sleep(0.14)
        assert controller.engine.tick == tick_at_stop

        # Start after stop works and reset while running stops loop and restores baseline
        s5 = await controller.start()
        assert s5.running is True
        controller.inject_scenario("db_latency_cascade")
        controller.advance(ticks=4)
        assert controller.engine.get_status(running=True).active_incidents_count == 1

        reset_status = await controller.reset(clear_incidents=True)
        assert reset_status.running is False
        assert controller._task is None
        assert reset_status.tick == 0
        assert reset_status.sim_time_s == 0.0
        assert reset_status.active_scenario is None
        assert reset_status.healthy_services == 7
        assert reset_status.active_incidents_count == 0
        assert reset_status.resilience_score >= 95.0

    asyncio.run(_run())


def test_sqlite_audit_records_for_lifecycle_and_cascade(tmp_path: Path) -> None:
    """Verify SQLite audit_logs persist lifecycle and incident detection events in order."""
    db_file = tmp_path / "verify_audit.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    init_db(target_engine=test_engine)
    with TestSessionLocal() as db:
        seed_initial_data(db)

    app = create_app(initialize_db=False)

    def override_get_db():
        db: Session = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        assert client.post("/api/v1/simulation/start").status_code == 200
        # Repeated start should not emit a duplicate audit record
        assert client.post("/api/v1/simulation/start").status_code == 200
        assert client.post("/api/v1/simulation/stop").status_code == 200
        # Repeated stop should not emit a duplicate audit record
        assert client.post("/api/v1/simulation/stop").status_code == 200
        assert client.post("/api/v1/simulation/inject", json={"scenario_id": "db_latency_cascade"}).status_code == 202
        assert client.post("/api/v1/simulation/advance", json={"ticks": 6}).status_code == 200
        assert client.post("/api/v1/simulation/reset", json={"clear_incidents": True}).status_code == 200

    with TestSessionLocal() as db:
        rows = db.execute(select(AuditLogORM).order_by(AuditLogORM.timestamp.asc())).scalars().all()

    actions = [r.action for r in rows]
    assert actions == [
        "SIMULATION_STARTED",
        "SIMULATION_STOPPED",
        "SCENARIO_INJECTED",
        "INCIDENT_DETECTED",
        "SIMULATION_RESET",
    ]
    inc_row = rows[3]
    assert inc_row.incident_id == "INC-0001"
    assert inc_row.actor_type == "SYSTEM"
    assert inc_row.actor_name == "IncidentDetector"
    assert inc_row.details["root_cause_candidate"] == "postgres-primary"
    test_engine.dispose()


def test_background_tick_loop_persists_incident_detected_audit(tmp_path: Path) -> None:
    """Verify background tick loop persists INCIDENT_DETECTED once to SQLite and stops cleanly."""
    db_file = tmp_path / "bg_audit.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    TestSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    init_db(target_engine=test_engine)
    with TestSessionLocal() as db:
        seed_initial_data(db)

    async def _run() -> None:
        controller = SimulationController(
            tick_interval_seconds=0.04,
            session_factory=TestSessionLocal,
        )
        with TestSessionLocal() as db:
            await controller.start(db=db)
            controller.inject_scenario("db_latency_cascade", db=db)

        # Wait deterministically until background ticks detect the incident and advance at least 2 ticks
        deadline = asyncio.get_running_loop().time() + 2.0
        while controller.engine.tick < 3 and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.02)

        assert controller.engine.tick >= 3
        assert len(controller.list_incidents()) == 1

        # Reset while running should stop loop and record stopped_running_loop=True
        with TestSessionLocal() as db:
            reset_status = await controller.reset(clear_incidents=True, db=db)
        assert reset_status.running is False
        assert controller._task is None

    asyncio.run(_run())

    with TestSessionLocal() as db:
        rows = db.execute(select(AuditLogORM).order_by(AuditLogORM.timestamp.asc())).scalars().all()

    detected_rows = [r for r in rows if r.action == "INCIDENT_DETECTED"]
    assert len(detected_rows) == 1
    row = detected_rows[0]
    assert row.incident_id == "INC-0001"
    assert row.actor_type == "SYSTEM"
    assert row.actor_name == "IncidentDetector"
    assert row.details["severity"] == "CRITICAL"
    assert row.details["root_cause_candidate"] == "postgres-primary"
    assert "postgres-primary" in row.details["affected_services"]
    assert row.details["tick"] == 1

    reset_rows = [r for r in rows if r.action == "SIMULATION_RESET"]
    assert len(reset_rows) == 1
    assert reset_rows[0].details["stopped_running_loop"] is True

    test_engine.dispose()

