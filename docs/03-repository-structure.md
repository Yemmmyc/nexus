# NEXUS — Proposed Repository Structure

**Project:** NEXUS — Autonomous Infrastructure Resilience & Trust Engine  
**Version:** 1.0 (MVP)

---

## 1. Directory Layout

```text
nexus/
├── docs/                                # Architecture, PRD, contracts & planning docs
│   ├── 01-prd.md
│   ├── 02-architecture.md
│   ├── 03-repository-structure.md
│   ├── 04-api-endpoints.md
│   ├── 05-data-models.md
│   ├── 06-agent-contracts.md
│   └── 07-implementation-plan.md
│
├── backend/                             # Python FastAPI modular monolith
│   ├── app/
│   │   ├── main.py                      # FastAPI app entrypoint, lifespan, CORS, routers
│   │   ├── config.py                    # Pydantic Settings (AI mode, DB path, tick interval)
│   │   ├── db/
│   │   │   ├── database.py              # SQLite + SQLAlchemy 2.0 engine & session factory
│   │   │   ├── models.py                # ORM table definitions
│   │   │   └── seed.py                  # Default 7-service topology & policy rules seed
│   │   ├── schemas/                     # Pydantic v2 API & internal contracts
│   │   │   ├── topology.py              # ServiceNode, DependencyEdge, HealthSnapshot
│   │   │   ├── telemetry.py             # MetricSample, MonitoringEvent
│   │   │   ├── incident.py              # Incident, Investigation, RiskAssessment
│   │   │   ├── remediation.py           # RemediationPlan, ActionStep, TrustVerdict
│   │   │   ├── agent.py                 # AgentRun, AgentStepTrace
│   │   │   └── audit.py                 # AuditLogEntry, DashboardSummary
│   │   ├── simulator/                   # Local infrastructure simulation & fault injection
│   │   │   ├── topology_graph.py        # Directed graph utilities (upstream/downstream/blast radius)
│   │   │   ├── engine.py                # Tick-based metric propagation & fault state machine
│   │   │   ├── scenarios.py             # Built-in scenarios (db_latency_cascade, etc.)
│   │   │   └── actions.py               # Static allowlisted simulated remediation handlers
│   │   ├── agents/                      # Lightweight logical agent implementations
│   │   │   ├── base.py                  # BaseAgent protocol & execution wrapper
│   │   │   ├── observer.py              # Alert detection & event correlation
│   │   │   ├── investigator.py          # Evidence-grounded RCA (LLM + deterministic fallback)
│   │   │   ├── llm_client.py            # Optional structured JSON LLM adapter
│   │   │   ├── risk.py                  # Blast radius & composite risk scoring
│   │   │   ├── recovery.py              # Allowlisted remediation plan generator
│   │   │   ├── trust.py                 # Declarative safety & policy gate
│   │   │   ├── verification.py          # Post-remediation SLO verification loop
│   │   │   └── orchestrator.py          # Coordinates pipeline & persists agent traces
│   │   ├── services/                    # Application services & event broadcasting
│   │   │   ├── audit_service.py         # Append-only audit trail writer
│   │   │   ├── resilience_service.py    # Resilience score calculation & executive KPIs
│   │   │   └── event_bus.py             # In-process async pub/sub feeding SSE clients
│   │   └── api/                         # FastAPI route modules (/api/v1/*)
│   │       ├── router.py                # Root v1 router aggregation
│   │       ├── dashboard.py             # Overview, resilience score, topology
│   │       ├── simulation.py            # Start/stop/reset, inject fault, list scenarios
│   │       ├── incidents.py             # List/get incidents, trigger investigation
│   │       ├── remediations.py          # Approve/reject/execute plans, list policies
│   │       ├── audit.py                 # Query audit logs & agent runs
│   │       └── stream.py                # SSE live event stream (/api/v1/stream)
│   ├── tests/                           # Pytest suite
│   │   ├── conftest.py                  # In-memory SQLite test fixtures
│   │   ├── test_simulator.py            # Cascading failure propagation & recovery tests
│   │   ├── test_agents.py               # Observer, Investigator (deterministic), Risk, Trust tests
│   │   └── test_e2e_api.py              # Full incident lifecycle API integration test
│   ├── pyproject.toml                   # Python dependencies & pytest config
│   ├── requirements.txt                 # Pinned pip requirements for fast Docker builds
│   └── Dockerfile
│
├── frontend/                            # React + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── main.tsx                     # App bootstrap
│   │   ├── App.tsx                      # Root shell, layout & SSE connection provider
│   │   ├── index.css                    # Tailwind directives & custom design tokens
│   │   ├── api/
│   │   │   ├── client.ts                # Typed fetch wrapper for /api/v1/*
│   │   │   └── stream.ts                # SSE EventSource hook with auto-reconnect
│   │   ├── types/
│   │   │   └── nexus.ts                 # TypeScript interfaces mirroring Pydantic schemas
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── TopBar.tsx           # Branding, scenario controls, AI mode toggle, live status
│   │   │   │   └── ExecutiveStrip.tsx   # Resilience score, active incidents, severity, health
│   │   │   ├── graph/
│   │   │   │   ├── DependencyGraph.tsx  # React Flow canvas, blast radius highlight, legend
│   │   │   │   └── ServiceNodeCard.tsx  # Custom node showing health, p99 latency, error rate
│   │   │   ├── investigation/
│   │   │   │   ├── IncidentList.tsx     # Active & historical incidents selector
│   │   │   │   ├── InvestigationPanel.tsx # RCA hypothesis, cited evidence, confidence, limits
│   │   │   │   └── AgentActivityFeed.tsx  # Live 6-agent pipeline trace
│   │   │   ├── recovery/
│   │   │   │   ├── RecoveryPanel.tsx    # Proposed actions, policy verdict, Approve/Reject CTA
│   │   │   │   └── VerificationStatus.tsx # Post-action SLO check progress
│   │   │   └── audit/
│   │   │       └── AuditTimeline.tsx    # Filterable chronological audit log
│   │   └── utils/
│   │       └── formatters.ts            # Latency, timestamps, severity colors, badges
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── nginx.conf                       # Reverse proxy /api + SSE config for Docker
│   └── Dockerfile
│
├── docker-compose.yml                   # Local one-command full-stack orchestration
├── .env.example                         # Optional LLM_API_KEY, NEXUS_AI_MODE, ports
├── .gitignore
└── README.md                            # Quickstart, demo walkthrough, architecture summary
```

---

## 2. Key Structural Decisions

- **No Monorepo Tooling Overhead:** Plain `backend/` and `frontend/` directories avoid Turborepo/Nx complexity while keeping Docker builds and local development straightforward.
- **Mirroring Schemas:** `backend/app/schemas/` is the source of truth for API contracts, mirrored cleanly in `frontend/src/types/nexus.ts`.
- **Isolated `simulator/` and `agents/`:** The simulator has zero dependency on the agents, and agents interact with the simulator only through read-only telemetry interfaces or the policy-gated `actions.py` allowlist.
- **SQLite Data Volume:** Local database file (`backend/data/nexus.db`, gitignored) persists audit history across refreshes and restarts, with a one-click `POST /api/v1/simulation/reset` endpoint to restore a clean demo state.

