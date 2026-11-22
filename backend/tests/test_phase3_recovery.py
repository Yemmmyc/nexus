"""Phase 3 tests for Recovery Catalog, Recovery Agent, Trust Policy, Approval, Execution, and Verification."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.trust import TrustAgent
from app.db.database import build_engine, get_db, init_db
from app.db.models import AuditLogORM, IncidentORM, RemediationPlanORM
from app.db.seed import seed_initial_data
from app.main import create_app
from app.schemas.investigation import (
    BlastRadiusAssessment,
    ConfidenceAssessment,
    ConfidenceCriterion,
    InvestigationResult,
)
from app.schemas.simulation import DetectedIncident
from app.simulator.engine import SimulationEngine


def _make_isolated_client(tmp_path: Path, name: str):
    db_file = tmp_path / f"{name}.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    TestSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
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
    return app, test_engine, TestSessionLocal


def test_trust_agent_policy_rules_and_reproducibility() -> None:
    """Verify DENY, REQUIRE_HUMAN_APPROVAL, AUTO_APPROVE, and deterministic reproducibility."""
    engine = SimulationEngine()
    engine.inject_scenario("db_latency_cascade")
    engine.step(ticks=5)
    inc = engine.detector.list_incidents()[0]
    trust = TrustAgent()
    now = datetime.now(timezone.utc)

    high_conf_inv = InvestigationResult(
        id="INV-TEST",
        incident_id=inc.id,
        status="COMPLETED",
        inference_mode="DETERMINISTIC",
        model_name="test",
        summary="summary",
        root_cause_hypothesis="hypothesis",
        probable_root_cause_service="postgres-primary",
        supporting_evidence=[],
        limiting_evidence=[],
        affected_services=inc.affected_services,
        service_roles=[],
        contributing_factors=[],
        blast_radius=BlastRadiusAssessment(
            risk_score=40,
            risk_level="MEDIUM",
            impacted_services=["worker-fulfillment"],
            unaffected_services=["auth-service"],
            impacted_service_count=1,
            total_service_count=7,
            customer_facing_impact=False,
            business_impact_summary="contained",
            factors={},
        ),
        confidence=ConfidenceAssessment(
            score=0.88,
            level="HIGH",
            criteria=[
                ConfidenceCriterion(name="c1", score=0.88, weight=1.0, explanation="ok")
            ],
        ),
        recommended_next_steps=[],
        agent_trace=[],
        created_at=now,
        updated_at=now,
    )

    # POL-001: Unknown action -> DENY
    r1 = trust.evaluate(
        action_id="run_arbitrary_shell",
        target_service="postgres-primary",
        parameters={},
        evidence_refs=["EVID-EVT-00001"],
        incident=inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r1.decision == "DENY"
    assert r1.matched_rules[0].rule_id == "POL-001"

    # POL-002: Invalid target for action -> DENY
    r2 = trust.evaluate(
        action_id="expand_db_connection_pool",
        target_service="api-gateway",
        parameters={"pool_multiplier": 2.0},
        evidence_refs=["EVID-EVT-00001"],
        incident=inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r2.decision == "DENY"
    assert r2.matched_rules[0].rule_id == "POL-002"

    # POL-003: Parameter out of bounds -> DENY
    r3 = trust.evaluate(
        action_id="expand_db_connection_pool",
        target_service="postgres-primary",
        parameters={"pool_multiplier": 99.0},
        evidence_refs=["EVID-EVT-00001"],
        incident=inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r3.decision == "DENY"
    assert r3.matched_rules[0].rule_id == "POL-003"

    # POL-004: Missing evidence -> DENY
    r4 = trust.evaluate(
        action_id="expand_db_connection_pool",
        target_service="postgres-primary",
        parameters={"pool_multiplier": 2.0},
        evidence_refs=[],
        incident=inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r4.decision == "DENY"
    assert r4.matched_rules[0].rule_id == "POL-004"

    # POL-005: Precondition failed (incident already RESOLVED) -> DENY
    resolved_inc = inc.model_copy(update={"status": "RESOLVED"})
    r5 = trust.evaluate(
        action_id="expand_db_connection_pool",
        target_service="postgres-primary",
        parameters={"pool_multiplier": 2.0},
        evidence_refs=["EVID-EVT-00001"],
        incident=resolved_inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r5.decision == "DENY"
    assert r5.matched_rules[0].rule_id == "POL-005"

    # POL-006/POL-007: DB tier + CRITICAL severity -> REQUIRE_HUMAN_APPROVAL
    r6 = trust.evaluate(
        action_id="expand_db_connection_pool",
        target_service="postgres-primary",
        parameters={"pool_multiplier": 2.0},
        evidence_refs=["EVID-EVT-00001"],
        incident=inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r6.decision == "REQUIRE_HUMAN_APPROVAL"
    assert any(m.rule_id == "POL-006" for m in r6.matched_rules)

    # Reproducibility check
    r6_repeat = trust.evaluate(
        action_id="expand_db_connection_pool",
        target_service="postgres-primary",
        parameters={"pool_multiplier": 2.0},
        evidence_refs=["EVID-EVT-00001"],
        incident=inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r6.decision == r6_repeat.decision
    assert [m.rule_id for m in r6.matched_rules] == [m.rule_id for m in r6_repeat.matched_rules]

    # POL-008: LOW/MEDIUM severity non-DB action with high confidence -> AUTO_APPROVE
    medium_inc = DetectedIncident(
        **{**inc.model_dump(), "severity": "MEDIUM"}
    )
    r8 = trust.evaluate(
        action_id="scale_queue_consumers",
        target_service="worker-fulfillment",
        parameters={"consumer_multiplier": 2.4},
        evidence_refs=["EVID-EVT-00004"],
        incident=medium_inc,
        investigation=high_conf_inv,
        engine=engine,
    )
    assert r8.decision == "AUTO_APPROVE"
    assert r8.matched_rules[0].rule_id == "POL-008"


def test_full_e2e_detect_investigate_plan_approve_execute_verify_resolve(tmp_path: Path) -> None:
    """End-to-end API test of the complete policy-gated simulated recovery and multi-tick verification loop."""
    app, test_engine, TestSessionLocal = _make_isolated_client(tmp_path, "phase3_e2e")

    with TestClient(app) as client:
        # 1. Catalog check
        cat_resp = client.get("/api/v1/remediations/catalog")
        assert cat_resp.status_code == 200
        action_ids = {a["action_id"] for a in cat_resp.json()["actions"]}
        assert action_ids == {
            "expand_db_connection_pool",
            "enable_circuit_breaker",
            "scale_queue_consumers",
        }

        # 2. Inject cascade and advance 6 ticks
        assert client.post("/api/v1/simulation/inject", json={"scenario_id": "db_latency_cascade"}).status_code == 202
        assert client.post("/api/v1/simulation/advance", json={"ticks": 6}).status_code == 200

        inc_id = client.get("/api/v1/incidents").json()["incidents"][0]["id"]
        assert client.post(f"/api/v1/incidents/{inc_id}/investigate").status_code == 200

        # 3. Recovery Agent proposes plan & Trust Agent evaluates policy
        plan_resp = client.post(f"/api/v1/incidents/{inc_id}/remediations")
        assert plan_resp.status_code == 201
        plan = plan_resp.json()
        plan_id = plan["id"]
        assert plan["action_id"] == "expand_db_connection_pool"
        assert plan["target_service"] == "postgres-primary"
        assert len(plan["evidence_refs"]) >= 1
        assert plan["policy_decision"] == "REQUIRE_HUMAN_APPROVAL"
        assert plan["approval_status"] == "PENDING"
        assert plan["execution_status"] == "NOT_STARTED"

        # List & get plan endpoints
        assert len(client.get(f"/api/v1/remediations?incident_id={inc_id}").json()["plans"]) == 1
        assert client.get(f"/api/v1/remediations/{plan_id}").status_code == 200

        # Re-evaluate endpoint works before execution
        eval_resp = client.post(f"/api/v1/remediations/{plan_id}/evaluate")
        assert eval_resp.status_code == 200
        assert eval_resp.json()["policy_decision"] == "REQUIRE_HUMAN_APPROVAL"

        # 4. Execution MUST be blocked while approval is PENDING
        blocked_exec = client.post(f"/api/v1/remediations/{plan_id}/execute")
        assert blocked_exec.status_code == 403

        # 5. Human approval succeeds; duplicate approval returns 409
        approve_resp = client.post(
            f"/api/v1/remediations/{plan_id}/approve",
            json={"actor": "sre-lead", "comment": "Evidence confirms DB pool saturation."},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["approval_status"] == "APPROVED"
        assert approve_resp.json()["approved_by"] == "sre-lead"

        dup_approve = client.post(
            f"/api/v1/remediations/{plan_id}/approve",
            json={"actor": "sre-lead", "comment": "duplicate"},
        )
        assert dup_approve.status_code == 409

        # 6. Execute approved simulated recovery; duplicate execution returns 409
        exec_resp = client.post(f"/api/v1/remediations/{plan_id}/execute")
        assert exec_resp.status_code == 200
        assert exec_resp.json()["execution_status"] == "COMPLETED"
        assert exec_resp.json()["verification_status"] == "IN_PROGRESS"

        dup_exec = client.post(f"/api/v1/remediations/{plan_id}/execute")
        assert dup_exec.status_code == 409

        exec_get = client.get(f"/api/v1/remediations/{plan_id}/execution")
        assert exec_get.status_code == 200
        assert exec_get.json()["execution_identifier"] == "sim.exec.expand_db_connection_pool"

        # 7. Verification immediately after execution (1 tick) is still IN_PROGRESS; incident NOT yet RESOLVED
        assert client.post("/api/v1/simulation/advance", json={"ticks": 1}).status_code == 200
        v1 = client.get(f"/api/v1/remediations/{plan_id}/verification").json()
        assert v1["status"] == "IN_PROGRESS"
        assert client.get(f"/api/v1/incidents/{inc_id}").json()["status"] != "RESOLVED"

        # 8. Advance further ticks so recovery unfolds smoothly across topology & queue and holds 2 consecutive ticks
        final_ver = v1
        for _ in range(9):
            assert client.post("/api/v1/simulation/advance", json={"ticks": 1}).status_code == 200
            final_ver = client.get(f"/api/v1/remediations/{plan_id}/verification").json()
            if final_ver["status"] == "VERIFIED":
                break

        assert final_ver["status"] == "VERIFIED"
        assert final_ver["consecutive_healthy_ticks"] >= 2
        assert final_ver["resilience_score"] >= 90.0

        # Incident is now RESOLVED only after successful verification
        inc_after = client.get(f"/api/v1/incidents/{inc_id}").json()
        assert inc_after["status"] == "RESOLVED"

    # Verify SQLite persistence and full audit trail
    with TestSessionLocal() as db:
        plans = db.execute(select(RemediationPlanORM)).scalars().all()
        inc_row = db.get(IncidentORM, inc_id)
        audit_actions = [
            r.action
            for r in db.execute(
                select(AuditLogORM)
                .where(AuditLogORM.incident_id == inc_id)
                .order_by(AuditLogORM.timestamp.asc())
            )
            .scalars()
            .all()
        ]

    assert len(plans) == 1
    assert plans[0].verification_status == "VERIFIED"
    assert inc_row is not None and inc_row.status == "RESOLVED"
    for expected_action in [
        "INCIDENT_DETECTED",
        "INVESTIGATION_STARTED",
        "INVESTIGATION_COMPLETED",
        "REMEDIATION_PLAN_CREATED",
        "POLICY_EVALUATED",
        "REMEDIATION_APPROVED",
        "REMEDIATION_EXECUTION_STARTED",
        "REMEDIATION_EXECUTION_COMPLETED",
        "VERIFICATION_STARTED",
        "VERIFICATION_COMPLETED",
        "INCIDENT_RESOLVED",
    ]:
        assert expected_action in audit_actions

    test_engine.dispose()


def test_denied_plan_and_rejection_guards_and_failed_verification(tmp_path: Path) -> None:
    """Verify DENIED plans cannot be approved/executed, rejections block execution, and insufficient recovery fails verification."""
    app, test_engine, TestSessionLocal = _make_isolated_client(tmp_path, "phase3_guards")

    with TestClient(app) as client:
        assert client.post("/api/v1/simulation/inject", json={"scenario_id": "db_latency_cascade"}).status_code == 202
        assert client.post("/api/v1/simulation/advance", json={"ticks": 6}).status_code == 200
        inc_id = client.get("/api/v1/incidents").json()["incidents"][0]["id"]

        # 1. Unknown action -> DENIED; cannot be approved or executed
        denied_plan = client.post(
            f"/api/v1/incidents/{inc_id}/remediations",
            json={"action_id": "drop_database_shell"},
        ).json()
        assert denied_plan["policy_decision"] == "DENY"
        assert denied_plan["approval_status"] == "DENIED"
        assert client.post(f"/api/v1/remediations/{denied_plan['id']}/approve").status_code == 403
        assert client.post(f"/api/v1/remediations/{denied_plan['id']}/execute").status_code == 403

        # 2. Valid plan -> Rejected by human -> duplicate rejection 409 & execution blocked 403
        rej_plan = client.post(f"/api/v1/incidents/{inc_id}/remediations").json()
        assert client.post(
            f"/api/v1/remediations/{rej_plan['id']}/reject",
            json={"actor": "sre-operator", "comment": "Prefer manual check."},
        ).status_code == 200
        assert client.post(f"/api/v1/remediations/{rej_plan['id']}/reject").status_code == 409
        assert client.post(f"/api/v1/remediations/{rej_plan['id']}/execute").status_code == 403

        # 3. Insufficient remediation (only circuit breaker on payment-service during DB failure)
        #    -> approved & executed, but postgres-primary remains critical -> Verification FAILED & incident stays unresolved!
        cb_plan = client.post(
            f"/api/v1/incidents/{inc_id}/remediations",
            json={"action_id": "enable_circuit_breaker", "target_service": "payment-service"},
        ).json()
        assert cb_plan["policy_decision"] == "REQUIRE_HUMAN_APPROVAL"
        assert client.post(f"/api/v1/remediations/{cb_plan['id']}/approve").status_code == 200
        assert client.post(f"/api/v1/remediations/{cb_plan['id']}/execute").status_code == 200

        # Advance 10 ticks (exceeds max_verification_ticks)
        assert client.post("/api/v1/simulation/advance", json={"ticks": 10}).status_code == 200
        ver_fail = client.get(f"/api/v1/remediations/{cb_plan['id']}/verification").json()
        assert ver_fail["status"] == "FAILED"
        assert client.get(f"/api/v1/incidents/{inc_id}").json()["status"] != "RESOLVED"

    with TestSessionLocal() as db:
        actions = [
            r.action
            for r in db.execute(select(AuditLogORM).where(AuditLogORM.incident_id == inc_id)).scalars().all()
        ]
    assert "REMEDIATION_REJECTED" in actions
    assert "VERIFICATION_FAILED" in actions
    assert "INCIDENT_RESOLVED" not in actions

    test_engine.dispose()

