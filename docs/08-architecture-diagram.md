# NEXUS — Actual-Implementation System Architecture

**Project:** NEXUS — Autonomous Infrastructure Resilience & Trust Engine  
**Tagline:** *Predict. Investigate. Recover. Verify.*  
**Baseline:** Commit `061e47a` (Phases 0 – 4C Complete)

---

## 1. End-to-End Runtime & Container Architecture

The diagram below reflects the exact implemented architecture running under `docker compose up --build`, with zero hypothetical components or external cloud dependencies.

```mermaid
flowchart TB
    User["Operator / Judge Browser\nFrontend: http://localhost:5173\nAPI / Docs: http://localhost:8010/docs"]

    subgraph DockerHost["Docker Compose Local Deployment (Bridge Network: nexus_net)"]
        subgraph FE["Container: nexus-frontend (nginx:1.27-alpine, port 5173 -> 80)"]
            Nginx["Nginx Reverse Proxy\nDynamic DNS: 127.0.0.11\n/api/* -> http://backend:8010"]
            SPA["React 18 + TypeScript + Vite + Tailwind SPA\n• Overview & Simulation Controls\n• Interactive Topology (@xyflow/react)\n• Incidents & Recovery Operations\n• Persisted Audit Timeline"]
        end

        subgraph BE["Container: nexus-backend (python:3.11-slim, non-root user, port 8010)"]
            FastAPI["FastAPI Application (/api/v1)\nhealth · simulation · topology\nincidents · remediations · audit"]

            subgraph SimLayer["Deterministic Simulation Engine (Phase 1)"]
                SimEngine["SimulationEngine\n7 Services · 8 Directed Edges\n2s Tick Loop / Deterministic Advance"]
                Prop["Mathematical Propagation\nFault Pressure Ramp · Topology Weights\nQueue Conservation of Flow"]
                Det["IncidentDetector\nSLO Thresholds · Connected Correlation\nDeterministic Root-Cause Candidate"]
            end

            subgraph IntelLayer["Incident Intelligence Pipeline (Phase 2)"]
                Obs["ObserverAgent\nTraceable EVID-* Bundle"]
                Inv["InvestigatorAgent\nDeterministic Causal Engine\n4-Criterion Confidence Rubric"]
                LLM["OptionalLLMAdapter (Read-Only)\nStructured JSON + Evidence-ID Validation\nAutomatic Deterministic Fallback"]
                Risk["RiskAnalystAgent\nBlast Radius & 0-100 Risk Score"]
            end

            subgraph RecLayer["Policy-Gated Recovery & Verification (Phase 3)"]
                Catalog["Static Allowlisted Catalog\nexpand_db_connection_pool\nenable_circuit_breaker\nscale_queue_consumers"]
                RecAgent["RecoveryAgent\nStructured Plan Builder"]
                Trust["TrustAgent (Policy Gate)\nDeclarative Rules POL-001..POL-008\nAUTO_APPROVE | REQUIRE_HUMAN_APPROVAL | DENY"]
                HumanGate{{"Human Approval Boundary\nPOST /remediations/{id}/approve|reject"}}
                Exec["SimulatedRecoveryExecutor\nAllowlist + Policy + Approval Validation\nApplies ActiveMitigation to Simulator"]
                Ver["VerificationAgent\nMulti-Tick SLO Stability Check\n2 Consecutive Healthy Ticks -> RESOLVED"]
            end

            AuditSvc["AuditService (Append-Only)\n20 Distinct Persisted Lifecycle Actions"]
        end

        Vol[("Persistent Docker Volume\nnexus_sqlite_data -> /app/data/nexus.db\nSQLite (SQLAlchemy 2.0)\nservices · dependencies · incidents\ninvestigations · remediation_plans · audit_logs")]
    end

    User -->|"HTTP :5173"| Nginx
    User -.->|"Direct API / Swagger :8010"| FastAPI
    Nginx --> SPA
    Nginx -->|"/api/* over nexus_net"| FastAPI

    FastAPI --> SimEngine
    SimEngine --> Prop
    Prop --> Det

    FastAPI --> Obs
    Obs --> Inv
    Inv -.->|"Optional when NEXUS_LLM_API_KEY set"| LLM
    Inv --> Risk

    FastAPI --> RecAgent
    Catalog --> RecAgent
    RecAgent --> Trust
    Trust -->|"REQUIRE_HUMAN_APPROVAL"| HumanGate
    HumanGate -->|"Approved"| Exec
    Trust -->|"AUTO_APPROVE"| Exec
    Catalog --> Exec
    Exec -->|"Register ActiveMitigation"| SimEngine
    Exec --> Ver
    Ver -->|"Inspect Telemetry History"| SimEngine

    SimEngine --> AuditSvc
    Inv --> AuditSvc
    RecAgent --> AuditSvc
    Trust --> AuditSvc
    HumanGate --> AuditSvc
    Exec --> AuditSvc
    Ver --> AuditSvc
    AuditSvc --> Vol
    FastAPI --> Vol
```

---

## 2. Simulated Service Dependency Topology (7 Services · 8 Directed Edges)

```mermaid
flowchart LR
    GW["api-gateway\n(edge)"]
    AUTH["auth-service\n(application — isolated from DB)"]
    CHK["checkout-api\n(application)"]
    PAY["payment-service\n(application)"]
    Q["order-queue\n(messaging)"]
    WRK["worker-fulfillment\n(worker)"]
    PG["postgres-primary\n(database — cascade origin)"]

    GW -->|"gRPC"| AUTH
    GW -->|"HTTP"| CHK
    CHK -->|"gRPC"| PAY
    CHK -->|"AMQP"| Q
    CHK -->|"TCP/Postgres"| PG
    PAY -->|"TCP/Postgres"| PG
    WRK -->|"AMQP"| Q
    WRK -->|"TCP/Postgres"| PG
```

---

## 3. Trust & Safety Boundaries

1. **Zero Real Infrastructure Execution:** `SimulatedRecoveryExecutor` only registers bounded `ActiveMitigation` parameters inside `SimulationEngine`. No shell commands, scripts, Kubernetes APIs, or cloud calls exist.
2. **Static Action Allowlist:** Only the 3 actions in `backend/app/recovery/catalog.py` can be approved or executed; unknown actions or out-of-bounds parameters are denied by `TrustAgent` (`POL-001`–`POL-003`).
3. **Separation of Recommendation and Execution:** `RecoveryAgent` can only create plans; `TrustAgent` independently enforces `POL-001`–`POL-008`, and `DENY` decisions cannot be overridden by human approval.
4. **Authoritative Multi-Tick Verification:** Incidents transition to `RESOLVED` only after `VerificationAgent` observes 2 consecutive healthy ticks across all affected services and `order-queue < 250`.
5. **Immutable Auditability:** All 20 lifecycle actions are persisted in SQLite `audit_logs` inside the persistent `nexus_sqlite_data` Docker volume.
