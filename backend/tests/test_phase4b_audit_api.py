"""Phase 4B tests for persisted audit retrieval, chronological ordering, and incident isolation."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import build_engine, get_db, init_db
from app.db.seed import seed_initial_data
from app.main import create_app


def _make_client(tmp_path: Path):
    db_file = tmp_path / "phase4b_audit.db"
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
    return app, test_engine


def test_audit_endpoint_ordering_filtering_and_incident_isolation(tmp_path: Path) -> None:
    """GET /api/v1/audit returns persisted records in chronological order with incident/category/actor filters."""
    app, test_engine = _make_client(tmp_path)

    with TestClient(app) as client:
        # Initially empty
        empty = client.get("/api/v1/audit")
        assert empty.status_code == 200
        assert empty.json() == {"total": 0, "entries": []}

        # Run full governed lifecycle to generate real persisted audit records
        assert client.post("/api/v1/simulation/inject", json={"scenario_id": "db_latency_cascade"}).status_code == 202
        assert client.post("/api/v1/simulation/advance", json={"ticks": 6}).status_code == 200
        inc_id = client.get("/api/v1/incidents").json()["incidents"][0]["id"]
        assert client.post(f"/api/v1/incidents/{inc_id}/investigate").status_code == 200
        plan = client.post(f"/api/v1/incidents/{inc_id}/remediations").json()
        plan_id = plan["id"]
        assert client.post(
            f"/api/v1/remediations/{plan_id}/approve",
            json={"actor": "sre-operator", "comment": "Verified DB bottleneck."},
        ).status_code == 200
        assert client.post(f"/api/v1/remediations/{plan_id}/execute").status_code == 200

        for _ in range(10):
            assert client.post("/api/v1/simulation/advance", json={"ticks": 1}).status_code == 200
            ver = client.get(f"/api/v1/remediations/{plan_id}/verification").json()
            if ver["status"] == "VERIFIED":
                break

        # Ascending chronological order
        asc = client.get("/api/v1/audit?order=asc").json()
        assert asc["total"] >= 12
        timestamps = [e["timestamp"] for e in asc["entries"]]
        assert timestamps == sorted(timestamps)

        # Descending order reverses timestamps
        desc = client.get("/api/v1/audit?order=desc").json()
        desc_ts = [e["timestamp"] for e in desc["entries"]]
        assert desc_ts == sorted(desc_ts, reverse=True)

        # Incident isolation filter returns only records for inc_id (excludes SCENARIO_INJECTED with incident_id=None)
        inc_only = client.get(f"/api/v1/audit?incident_id={inc_id}&order=asc").json()
        assert inc_only["total"] >= 11
        assert all(e["incident_id"] == inc_id for e in inc_only["entries"])
        actions = [e["action"] for e in inc_only["entries"]]
        assert actions[0] == "INCIDENT_DETECTED"
        assert actions[-1] == "INCIDENT_RESOLVED"
        assert "POLICY_EVALUATED" in actions
        assert "REMEDIATION_APPROVED" in actions
        assert "REMEDIATION_EXECUTION_COMPLETED" in actions
        assert "VERIFICATION_COMPLETED" in actions

        # Non-existent incident returns empty list cleanly
        other_inc = client.get("/api/v1/audit?incident_id=INC-9999").json()
        assert other_inc["total"] == 0

        # Category filter (POLICY)
        policy_only = client.get(f"/api/v1/audit?incident_id={inc_id}&category=POLICY").json()
        assert policy_only["total"] == 2
        assert {e["action"] for e in policy_only["entries"]} == {
            "POLICY_EVALUATED",
            "REMEDIATION_APPROVED",
        }

        # Actor filter (HUMAN)
        human_only = client.get(f"/api/v1/audit?incident_id={inc_id}&actor_type=HUMAN").json()
        assert human_only["total"] == 1
        assert human_only["entries"][0]["action"] == "REMEDIATION_APPROVED"

    test_engine.dispose()
