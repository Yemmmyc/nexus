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

### `GET /api/v1/telemetry/history`
Returns recent metric samples for charting sparklines or service drill-down.
- **Query Params:** `service_id` (optional), `limit` (default `30`, max `120`)
- **Response (`200 OK`):** `{ "samples": [ /* MetricSample[] */ ] }`

---

## 2. Simulation Control Endpoints

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

### `POST /api/v1/simulation/inject`
Injects a failure scenario into the local simulator and triggers telemetry propagation.
- **Request Body:**
  ```json
  {
    "scenario_id": "db_latency_cascade"
  }
  ```
- **Response (`202 Accepted`):**
  ```json
  {
    "status": "injected",
    "scenario_id": "db_latency_cascade",
    "injected_at": "2026-11-21T18:30:02Z"
  }
  ```

### `POST /api/v1/simulation/reset`
Resets all simulated services to healthy baseline, clears active faults, and optionally clears non-archived active incidents. (Audit logs record the reset event.)
- **Request Body:** `{ "clear_history": false }`
- **Response (`200 OK`):** `{ "status": "reset", "resilience_score": 97.5 }`

### `POST /api/v1/settings/ai-mode`
Switches the Investigator AI mode for live demos (`auto`, `llm`, `deterministic`).
- **Request Body:** `{ "mode": "deterministic" }`
- **Response (`200 OK`):** `{ "ai_mode": "deterministic", "llm_available": false }`

---

## 3. Incident & Investigation Endpoints

### `GET /api/v1/incidents`
Lists incidents ordered by `created_at DESC`.
- **Query Params:** `status` (optional), `limit` (default `20`)
- **Response (`200 OK`):** `{ "incidents": [ /* IncidentSummary[] */ ] }`

### `GET /api/v1/incidents/{incident_id}`
Returns the full incident dossier: correlated events, investigation (RCA + evidence + confidence + limitations), risk assessment (blast radius), remediation plan, trust policy verdict, verification result, and agent run trace.
- **Response (`200 OK`):** `IncidentDetail` object (see `05-data-models.md`).
- **Errors:** `404 Not Found` if `incident_id` does not exist.

### `POST /api/v1/incidents/{incident_id}/reinvestigate`
Re-runs the Investigation -> Risk -> Recovery -> Trust pipeline for an active incident (useful for demonstrating LLM vs Deterministic comparison).
- **Response (`202 Accepted`):** `{ "incident_id": "...", "status": "INVESTIGATING" }`

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

