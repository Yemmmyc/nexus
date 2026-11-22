"""Phase 2 tests for incident persistence, evidence collection, deterministic & AI-fallback investigation, and APIs."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.investigator import InvestigatorAgent
from app.agents.llm_adapter import GroundingValidationError, LLMStructuredNarrative, OptionalLLMAdapter
from app.agents.observer import ObserverAgent
from app.agents.risk_analyst import RiskAnalystAgent
from app.config import Settings
from app.db.database import build_engine, get_db, init_db
from app.db.models import AuditLogORM, IncidentORM, InvestigationORM
from app.db.seed import seed_initial_data
from app.main import create_app
from app.simulator.engine import SimulationEngine


def _setup_cascade_engine(ticks: int = 6) -> tuple[SimulationEngine, str]:
    engine = SimulationEngine()
    engine.inject_scenario("db_latency_cascade")
    engine.step(ticks=ticks)
    inc = engine.detector.list_incidents()[0]
    return engine, inc.id


def test_observer_evidence_collection_and_traceable_ids() -> None:
    """Observer collects traceable non-fabricated evidence across events, telemetry, queue, and topology."""
    engine, inc_id = _setup_cascade_engine(ticks=6)
    inc = engine.detector.get_incident(inc_id)
    assert inc is not None

    bundle = ObserverAgent().collect(inc, engine)

    assert bundle.incident_id == inc_id
    assert bundle.detected_tick == 1
    assert bundle.detected_sim_time_s == 2.0
    assert "postgres-primary" in bundle.affected_services
    assert "auth-service" in bundle.unaffected_services
    assert len(bundle.items) >= 10

    source_types = {item.source_type for item in bundle.items}
    assert "monitoring_event" in source_types
    assert "telemetry_trend" in source_types
    assert "queue_metric" in source_types
    assert "topology_edge" in source_types
    assert "detector_candidate" in source_types

    # All evidence IDs must be unique and traceable
    ids = [item.evidence_id for item in bundle.items]
    assert len(ids) == len(set(ids))
    assert all(eid.startswith("EVID-") for eid in ids)


def test_deterministic_investigator_and_risk_analyst_findings() -> None:
    """Deterministic Investigator + Risk Analyst explain root cause, roles, blast radius, and confidence."""
    engine, inc_id = _setup_cascade_engine(ticks=6)
    inc = engine.detector.get_incident(inc_id)
    assert inc is not None

    bundle = ObserverAgent().collect(inc, engine)
    settings = Settings(ai_mode="deterministic")
    inv = InvestigatorAgent(settings=settings).investigate(bundle, engine.topology)
    blast = RiskAnalystAgent().assess(bundle, engine.topology)

    assert inv.inference_mode == "DETERMINISTIC"
    assert inv.probable_root_cause_service == "postgres-primary"
    assert "postgres-primary" in inv.root_cause_hypothesis
    assert len(inv.supporting_evidence) >= 5
    assert len(inv.limiting_evidence) >= 2
    assert len(inv.contributing_factors) >= 2
    assert len(inv.recommended_next_steps) >= 3

    roles_by_svc = {r.service_id: r.role for r in inv.service_roles}
    assert roles_by_svc["postgres-primary"] == "probable_root_cause"
    assert roles_by_svc["auth-service"] == "unaffected"
    assert roles_by_svc["payment-service"] == "downstream_symptom"
    assert roles_by_svc["checkout-api"] == "downstream_symptom"
    assert roles_by_svc["order-queue"] == "contributing_cause"

    # Explainable confidence criteria
    assert 0.75 <= inv.confidence.score <= 0.95
    assert inv.confidence.level == "HIGH"
    assert len(inv.confidence.criteria) == 4
    assert round(sum(c.weight for c in inv.confidence.criteria), 2) == 1.0

    # Blast radius & risk score
    assert blast.risk_score >= 75
    assert blast.risk_level == "CRITICAL"
    assert blast.customer_facing_impact is True
    assert blast.impacted_service_count == 6
    assert blast.total_service_count == 7
    assert "auth-service" in blast.unaffected_services


def test_ai_adapter_grounding_and_deterministic_fallback() -> None:
    """Investigator accepts grounded LLM output and falls back cleanly when AI fails or fabricates IDs."""
    engine, inc_id = _setup_cascade_engine(ticks=5)
    inc = engine.detector.get_incident(inc_id)
    assert inc is not None
    bundle = ObserverAgent().collect(inc, engine)
    valid_ids = [bundle.items[0].evidence_id, bundle.items[1].evidence_id]

    class GroundedFakeAdapter(OptionalLLMAdapter):
        def is_enabled(self) -> bool:
            return True

        def synthesize_narrative(self, _bundle):
            return LLMStructuredNarrative(
                summary="Grounded AI summary confirming postgres-primary bottleneck.",
                root_cause_hypothesis="Primary DB saturation caused downstream timeouts.",
                cited_evidence_ids=valid_ids,
                contributing_factors=["DB saturation above 85%"],
                recommended_next_steps=["Inspect postgres-primary connection pool"],
            )

    class HallucinatingFakeAdapter(OptionalLLMAdapter):
        def is_enabled(self) -> bool:
            return True

        def synthesize_narrative(self, _bundle):
            raise GroundingValidationError("LLM referenced ungrounded evidence IDs: EVID-FAKE-999")

    settings = Settings(ai_mode="auto", llm_api_key="test-key", llm_model="test-llm")

    # 1. Valid grounded LLM output is accepted and restricted to cited evidence IDs
    llm_out = InvestigatorAgent(settings=settings, llm_adapter=GroundedFakeAdapter(settings)).investigate(
        bundle, engine.topology
    )
    assert llm_out.inference_mode == "LLM"
    assert llm_out.model_name == "test-llm"
    assert [e.evidence_id for e in llm_out.supporting_evidence] == valid_ids

    # 2. Ungrounded/hallucinated LLM output triggers deterministic fallback with limitation note
    fallback_out = InvestigatorAgent(
        settings=settings, llm_adapter=HallucinatingFakeAdapter(settings)
    ).investigate(bundle, engine.topology)
    assert fallback_out.inference_mode == "DETERMINISTIC"
    assert fallback_out.probable_root_cause_service == "postgres-primary"
    assert any("GroundingValidationError" in note for note in fallback_out.limiting_evidence)


def test_phase2_incident_persistence_investigation_api_and_audit(tmp_path: Path) -> None:
    """End-to-end API test for incident persistence, evidence, investigation, timeline, and audit trail."""
    db_file = tmp_path / "phase2_api.db"
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

    with TestClient(app) as client:
        # Inject and advance deterministically
        assert client.post("/api/v1/simulation/inject", json={"scenario_id": "db_latency_cascade"}).status_code == 202
        assert client.post("/api/v1/simulation/advance", json={"ticks": 6}).status_code == 200

        # List and fetch persisted incident
        list_resp = client.get("/api/v1/incidents")
        assert list_resp.status_code == 200
        incidents = list_resp.json()["incidents"]
        assert len(incidents) == 1
        inc = incidents[0]
        inc_id = inc["id"]
        assert inc["investigation_status"] == "NOT_STARTED"
        assert inc["detected_sim_time_s"] == 2.0

        # Investigation GET before running returns 404
        assert client.get(f"/api/v1/incidents/{inc_id}/investigation").status_code == 404

        # Evidence endpoint works even before investigation is run
        ev_resp = client.get(f"/api/v1/incidents/{inc_id}/evidence")
        assert ev_resp.status_code == 200
        assert ev_resp.json()["incident_id"] == inc_id
        assert len(ev_resp.json()["items"]) >= 10

        # Trigger investigation
        inv_resp = client.post(f"/api/v1/incidents/{inc_id}/investigate")
        assert inv_resp.status_code == 200
        inv_body = inv_resp.json()
        assert inv_body["incident_id"] == inc_id
        assert inv_body["status"] == "COMPLETED"
        assert inv_body["inference_mode"] == "DETERMINISTIC"
        assert inv_body["probable_root_cause_service"] == "postgres-primary"
        assert len(inv_body["agent_trace"]) == 3
        assert [t["agent_role"] for t in inv_body["agent_trace"]] == [
            "Observer",
            "Investigator",
            "Risk Analyst",
        ]

        # Persisted investigation GET returns identical findings
        get_inv = client.get(f"/api/v1/incidents/{inc_id}/investigation")
        assert get_inv.status_code == 200
        assert get_inv.json()["id"] == inv_body["id"]

        # Incident record now reflects COMPLETED investigation status
        updated_inc = client.get(f"/api/v1/incidents/{inc_id}")
        assert updated_inc.status_code == 200
        assert updated_inc.json()["investigation_status"] == "COMPLETED"

        # Timeline combines monitoring events + SQLite audit events
        tl_resp = client.get(f"/api/v1/incidents/{inc_id}/timeline")
        assert tl_resp.status_code == 200
        tl_entries = tl_resp.json()["entries"]
        sources = {e["source"] for e in tl_entries}
        assert sources == {"MONITORING_EVENT", "AUDIT_LOG"}

    # Verify SQLite persistence directly
    with TestSessionLocal() as db:
        inc_rows = db.execute(select(IncidentORM)).scalars().all()
        inv_rows = db.execute(select(InvestigationORM)).scalars().all()
        audit_rows = db.execute(
            select(AuditLogORM)
            .where(AuditLogORM.incident_id == inc_id)
            .order_by(AuditLogORM.timestamp.asc())
        ).scalars().all()

    assert len(inc_rows) == 1
    assert len(inv_rows) == 1
    audit_actions = [r.action for r in audit_rows]
    assert "INCIDENT_DETECTED" in audit_actions
    assert "INVESTIGATION_STARTED" in audit_actions
    assert "INVESTIGATION_COMPLETED" in audit_actions
    assert "INCIDENT_UPDATED" in audit_actions

    test_engine.dispose()

