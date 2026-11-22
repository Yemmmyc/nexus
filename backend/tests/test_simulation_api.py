"""API integration tests for Phase 1 simulation controls, topology, telemetry, and incidents."""

from fastapi.testclient import TestClient


def test_simulation_scenarios_and_initial_status(client: TestClient) -> None:
    """GET /simulation/scenarios and /simulation/status expose db_latency_cascade and healthy baseline."""
    scen_resp = client.get("/api/v1/simulation/scenarios")
    assert scen_resp.status_code == 200
    scenarios = scen_resp.json()["scenarios"]
    assert any(s["id"] == "db_latency_cascade" for s in scenarios)

    status_resp = client.get("/api/v1/simulation/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["running"] is False
    assert body["tick"] == 0
    assert body["healthy_services"] == 7
    assert body["active_incidents_count"] == 0


def test_api_inject_advance_inspect_and_reset_flow(client: TestClient) -> None:
    """Full deterministic API flow: inject -> advance -> topology/telemetry/incidents -> reset."""
    # Inject scenario
    inject_resp = client.post(
        "/api/v1/simulation/inject",
        json={"scenario_id": "db_latency_cascade"},
    )
    assert inject_resp.status_code == 202
    assert inject_resp.json()["active_scenario"] == "db_latency_cascade"

    # Advance deterministically by 6 ticks (no sleep)
    adv_resp = client.post("/api/v1/simulation/advance", json={"ticks": 6})
    assert adv_resp.status_code == 200
    adv_body = adv_resp.json()
    assert adv_body["tick"] == 6
    assert adv_body["critical_services"] >= 1
    assert adv_body["active_incidents_count"] == 1
    assert adv_body["resilience_score"] < 80.0

    # Topology reflects blast radius and root cause candidate
    topo_resp = client.get("/api/v1/topology")
    assert topo_resp.status_code == 200
    nodes = {n["id"]: n for n in topo_resp.json()["nodes"]}
    assert nodes["postgres-primary"]["status"] == "critical"
    assert nodes["postgres-primary"]["is_root_cause_candidate"] is True
    assert nodes["auth-service"]["status"] == "healthy"

    # Telemetry history for postgres-primary contains tick 0..6
    hist_resp = client.get("/api/v1/telemetry/history?service_id=postgres-primary&limit=20")
    assert hist_resp.status_code == 200
    samples = hist_resp.json()["samples"]
    assert len(samples) == 7
    assert samples[-1]["metrics"]["latency_ms"] > samples[0]["metrics"]["latency_ms"] * 10

    # Incidents endpoint returns the correlated incident and detail route works
    inc_list = client.get("/api/v1/incidents")
    assert inc_list.status_code == 200
    incidents = inc_list.json()["incidents"]
    assert len(incidents) == 1
    inc_id = incidents[0]["id"]

    inc_detail = client.get(f"/api/v1/incidents/{inc_id}")
    assert inc_detail.status_code == 200
    assert inc_detail.json()["root_cause_candidate"] == "postgres-primary"
    assert inc_detail.json()["severity"] == "CRITICAL"

    # Reset restores healthy state
    reset_resp = client.post("/api/v1/simulation/reset", json={"clear_incidents": True})
    assert reset_resp.status_code == 200
    reset_body = reset_resp.json()
    assert reset_body["tick"] == 0
    assert reset_body["healthy_services"] == 7
    assert reset_body["active_incidents_count"] == 0


def test_api_start_stop_and_error_cases(client: TestClient) -> None:
    """Start/stop toggles running state and unknown scenario/incident return 404."""
    start_resp = client.post("/api/v1/simulation/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["running"] is True

    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["simulator_running"] is True

    stop_resp = client.post("/api/v1/simulation/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["running"] is False

    bad_scen = client.post("/api/v1/simulation/inject", json={"scenario_id": "nonexistent"})
    assert bad_scen.status_code == 404

    bad_inc = client.get("/api/v1/incidents/INC-9999")
    assert bad_inc.status_code == 404

