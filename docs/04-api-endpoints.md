# NEXUS — API Endpoint Definitions

**Base URL:** `/api/v1`  
**Content-Type:** `application/json` (except SSE stream: `text/event-stream`)  
**Versioning:** Path-prefixed (`/api/v1`)

---

## 1. System & Dashboard Endpoints

### `GET /api/v1/health`
Liveness and configuration status check.
- **Response (`200 OK`):**
  ```json
  {
    "status": "ok",
    "ai_mode": "deterministic",
    "llm_configured": false,
    "simulator_running": true,
    "db_connected": true
  }
  ```

### `GET /api/v1/dashboard/overview`
Returns aggregated executive KPIs for the dashboard header and summary widgets.
- **Response (`200 OK`):**
  ```json
  {
    "resilience_score": 62.5,
    "resilience_trend": "degrading",
    "active_incidents": 1,
    "resolved_incidents": 3,
    "severity_distribution": {
      "CRITICAL": 1,
      "HIGH": 0,
      "MEDIUM": 0,
      "LOW": 0
    },
    "infrastructure_health": {
      "total_services": 7,
      "healthy": 2,
      "degraded": 3,
      "critical": 2
    },
    "active_scenario": "db_latency_cascade",
    "ai_mode": "deterministic",
    "updated_at": "2026-11-21T18:30:00Z"
  }
  ```

### `GET /api/v1/topology`
Returns the service dependency graph with live per-node telemetry and optional blast-radius overlay for the active incident.
- **Query Params:** `incident_id` (optional string)
- **Response (`200 OK`):**
  ```json
  {
    "nodes": [
      {
        "id": "postgres-primary",
        "name": "Postgres Primary",
        "tier": "database",
        "status": "critical",
        "metrics": {
          "latency_ms": 1840.2,
          "error_rate": 0.14,
          "cpu_pct": 94.0,
          "saturation_pct": 98.5,
          "queue_depth": 0
        },
        "in_blast_radius": true,
        "is_probable_root_cause": true
      }
    ],
    "edges": [
      {
        "id": "e-pay-pg",
        "source": "payment-service",
        "target": "postgres-primary",
        "protocol": "tcp/postgres",
        "status": "critical",
        "latency_ms": 1840.2
      }
    ]
  }
  ```

### `GET /api/v1/telemetry`
Returns the latest telemetry sample for all services (or a single service).
- **Query Params:** `service_id` (optional)
- **Response (`200 OK`):** `{ "tick": 6, "samples": [ /* ServiceTelemetrySample[] */ ] }`

### `GET /api/v1/telemetry/history`
Returns recent metric samples for charting sparklines or service drill-down.
- **Query Params:** `service_id` (optional), `limit` (default `30`, max `120`)
- **Response (`200 OK`):** `{ "tick": 6, "samples": [ /* ServiceTelemetrySample[] */ ] }`

---

## 2. Simulation Control Endpoints

### `GET /api/v1/simulation/status`
Returns current simulation runtime state (running flag, tick, simulation time, active scenario, resilience score, service health counts, active incident count).

### `GET /api/v1/simulation/scenarios`
Lists available built-in failure scenarios.
- **Response (`200 OK`):**
  ```json
  {
    "scenarios": [
      {
        "id": "db_latency_cascade",
        "name": "Database Latency Cascade",
        "description": "Primary DB connection pool saturates, causing API timeouts, payment degradation, and order queue backlog.",
        "root_service": "postgres-primary",
        "expected_severity": "CRITICAL"
      }
    ]
  }
  ```

### `POST /api/v1/simulation/start`
Starts the periodic background simulation tick loop (~2s interval).
- **Response (`200 OK`):** `SimulationStatusResponse` (`running: true`)

### `POST /api/v1/simulation/stop`
Stops the periodic background simulation tick loop.
- **Response (`200 OK`):** `SimulationStatusResponse` (`running: false`)

### `POST /api/v1/simulation/advance`
Deterministically advances the simulation by `ticks` (`1..50`) without real-time waiting (enables reproducible testing and step-by-step demos).
- **Request Body:** `{ "ticks": 1 }`
- **Response (`200 OK`):** `SimulationStatusResponse`

### `POST /api/v1/simulation/inject`
Injects a failure scenario into the local simulator and triggers telemetry propagation on subsequent ticks.
- **Request Body:**
  ```json
  {
    "scenario_id": "db_latency_cascade"
  }
  ```
- **Response (`202 Accepted`):** `SimulationStatusResponse`

### `POST /api/v1/simulation/reset`
Stops any active loop, resets all simulated services to healthy baseline, clears active faults, and optionally clears incidents. (Audit logs record the reset event.)
- **Request Body:** `{ "clear_incidents": true }`
- **Response (`200 OK`):** `SimulationStatusResponse`

### `POST /api/v1/settings/ai-mode`
Switches the Investigator AI mode for live demos (`auto`, `llm`, `deterministic`).
- **Request Body:** `{ "mode": "deterministic" }`
- **Response (`200 OK`):** `{ "ai_mode": "deterministic", "llm_available": false }`

---

## 3. Incident & Investigation Endpoints

### `GET /api/v1/incidents`
Lists persisted incidents synced with the simulator, ordered newest first.
- **Response (`200 OK`):** `{ "incidents": [ /* DetectedIncident[] */ ] }`

### `GET /api/v1/incidents/{incident_id}`
Returns the persisted incident record (severity, lifecycle status, detection tick/time, root-cause candidate, affected services, supporting events, and `investigation_status`).
- **Response (`200 OK`):** `DetectedIncident`
- **Errors:** `404 Not Found` if `incident_id` does not exist.

### `POST /api/v1/incidents/{incident_id}/investigate`
Executes the 3-role logical investigation pipeline (`Observer` → `Investigator` → `Risk Analyst`), persists findings to SQLite, and records `INVESTIGATION_STARTED`, `INVESTIGATION_COMPLETED`, and `INCIDENT_UPDATED` audit events.
- **Response (`200 OK`):** `InvestigationResult`

### `GET /api/v1/incidents/{incident_id}/investigation`
Retrieves persisted investigation findings for an incident.
- **Response (`200 OK`):** `InvestigationResult`
- **Errors:** `404 Not Found` if incident does not exist or has not been investigated yet.

### `GET /api/v1/incidents/{incident_id}/evidence`
Retrieves the traceable `EvidenceBundle` (monitoring events, telemetry trends, queue metrics, topology edges, detector candidate) collected for an incident.
- **Response (`200 OK`):** `EvidenceBundle`

### `GET /api/v1/incidents/{incident_id}/timeline`
Returns a chronological timeline combining monitoring events and SQLite `audit_logs` entries for the incident.
- **Response (`200 OK`):** `IncidentTimelineResponse`

---

## 4. Remediation & Trust Policy Endpoints

### `GET /api/v1/policies`
Lists the active declarative safety & trust policies enforced by the Trust Agent.
- **Response (`200 OK`):** `{ "policies": [ /* PolicyRule[] */ ] }`

### `POST /api/v1/remediations/{plan_id}/approve`
Human operator approves a remediation plan that is `AWAITING_APPROVAL`, triggering controlled simulated execution followed by automatic verification.
- **Request Body:**
  ```json
  {
    "approved_by": "sre-operator",
    "comment": "Confirmed DB pool saturation from telemetry evidence; approved safe expansion."
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "plan_id": "plan-001",
    "status": "EXECUTING",
    "approved_by": "sre-operator",
    "approved_at": "2026-11-21T18:31:10Z"
  }
  ```
- **Errors:** `409 Conflict` if plan is not in `AWAITING_APPROVAL` state; `403 Forbidden` if Trust Agent verdict is `DENY`.

### `POST /api/v1/remediations/{plan_id}/reject`
Human operator rejects a proposed remediation plan. No simulated actions are executed.
- **Request Body:**
  ```json
  {
    "rejected_by": "sre-operator",
    "reason": "Prefer manual inspection before scaling DB pool."
  }
  ```
- **Response (`200 OK`):** `{ "plan_id": "plan-001", "status": "REJECTED" }`

---

## 5. Audit & Agent Activity Endpoints

### `GET /api/v1/audit`
Returns chronological audit trail entries (newest first).
- **Query Params:** `incident_id` (optional), `actor_type` (optional: `SYSTEM|AGENT|POLICY|HUMAN`), `limit` (default `50`)
- **Response (`200 OK`):** `{ "entries": [ /* AuditLogEntry[] */ ] }`

### `GET /api/v1/agents/activity`
Returns recent agent execution steps across all 6 roles.
- **Query Params:** `incident_id` (optional), `limit` (default `50`)
- **Response (`200 OK`):** `{ "runs": [ /* AgentRun[] */ ] }`

---

## 6. Real-Time Stream Endpoint (SSE)

### `GET /api/v1/stream`
Server-Sent Events stream pushing real-time updates to the dashboard without polling storms.

**Event Types:**
- `telemetry_tick`: Updated node metrics + resilience score (every ~2s)
- `event_created`: New monitoring alert generated
- `incident_updated`: Incident created or transitioned state
- `agent_step`: An agent started/completed a stage
- `remediation_updated`: Plan approved, step executed, or verification completed
- `audit_entry`: New audit record appended

**Wire Format Example:**
```text
event: agent_step
data: {"incident_id":"inc-101","agent":"Investigator","status":"completed","summary":"Identified postgres-primary connection pool saturation (confidence 0.92)","timestamp":"2026-11-21T18:30:06Z"}
```

