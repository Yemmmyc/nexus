# NEXUS — Prioritized Implementation Plan

**Timeline:** November 21 – November 30, 2026 (9 Days)  
**Strategy:** Vertical slice first. Get the full cascading failure -> investigation -> policy gate -> approval -> simulated recovery -> verification loop working end-to-end by **Day 5**, leaving **Days 6–9** for UI craft, polish, testing, and reproducible packaging.

---

## Priority Tiers

- **P0 (Must-Have for Demo):** Everything required for the end-to-end `db_latency_cascade` scenario, interactive dashboard, trust/policy gate, deterministic + LLM investigator, audit trail, and Docker Compose startup.
- **P1 (High-Value Polish):** Live SSE streaming, telemetry sparklines, AI mode toggle (`LLM` vs `Deterministic`) in UI, filterable audit timeline, automated pytest coverage.
- **P2 (Stretch — Only if P0 & P1 are rock-solid by Day 7):** Second fault scenario (e.g., `payment_gateway_timeout` or `queue_worker_stall`), JSON audit export.

---

## Milestone Schedule

### Phase 0: Project Scaffold & Foundation (Day 1 — Nov 21–22)
**Goal:** Both backend and frontend boot cleanly; SQLite DB initializes with the 7-service topology.
- [ ] Initialize `backend/` (FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite, `requirements.txt`, `config.py`).
- [ ] Initialize `frontend/` (Vite + React + TypeScript + Tailwind CSS + `@xyflow/react` + `lucide-react`).
- [ ] Create SQLite ORM models (`05-data-models.md`) and seed script for the 7-service topology + 5 default Trust policies.
- [ ] Add `GET /api/v1/health`, `GET /api/v1/topology`, and `.env.example`.
- **Exit Criteria:** `uvicorn` serves `/api/v1/topology` with 7 nodes & 8 edges; Vite renders a styled shell fetching live health.

### Phase 1: Infrastructure Simulator & Cascading Failure Engine (Days 2–3 — Nov 22–23)
**Goal:** Realistic local telemetry ticks and cascading failure propagation.
- [ ] Implement `TopologyGraph` helper (upstream/downstream traversal, blast radius calculation).
- [ ] Implement `SimulationEngine` background asyncio loop (2s ticks) generating baseline `MetricSample`s and threshold-based `MonitoringEvent`s.
- [ ] Implement `db_latency_cascade` scenario with mathematical propagation (`postgres-primary` -> `payment-service` & `checkout-api` -> `api-gateway`, `order-queue`, `worker-fulfillment`).
- [ ] Implement `ACTION_CATALOG` allowlisted simulated remediation handlers (`expand_db_connection_pool`, `enable_circuit_breaker`, `scale_queue_consumers`, etc.) that smoothly restore metrics over 3–5 ticks.
- [ ] Expose `/api/v1/simulation/scenarios`, `/inject`, `/reset`, and `resilience_service.py`.
- **Exit Criteria:** Injecting `db_latency_cascade` causes realistic cascading alerts across 5 services; calling the simulated actions restores healthy metrics. Unit tests in `test_simulator.py` pass.

### Phase 2: 6-Agent Pipeline, Trust Gate & Audit Trail (Days 3–4 — Nov 23–25)
**Goal:** Complete autonomous-yet-governed backend lifecycle.
- [ ] Implement `audit_service.py` (append-only SQLite logger) and `event_bus.py` (SSE pub/sub).
- [ ] Implement **Observer Agent** (time + topology alert correlation -> `Incident`).
- [ ] Implement **Investigator Agent** (deterministic root-cause engine + optional structured JSON `llm_client.py` with evidence citation validator and automatic fallback).
- [ ] Implement **Risk Agent** (blast radius + composite risk score 0–100).
- [ ] Implement **Recovery Agent** (allowlisted plan builder) & **Trust Agent** (declarative policy rules `POL-001`..`POL-005`).
- [ ] Implement **Verification Agent** (post-execution SLO check loop -> `RESOLVED` / `VERIFICATION_FAILED`).
- [ ] Wire `AgentOrchestrator` and expose `/api/v1/incidents/*`, `/api/v1/remediations/*/approve|reject`, `/api/v1/audit`, `/api/v1/agents/activity`, and `/api/v1/stream` (SSE).
- **Exit Criteria:** Full end-to-end integration test (`test_e2e_api.py`) injects fault -> verifies incident, RCA, risk, `AWAITING_APPROVAL` plan -> approves via API -> verifies `RESOLVED` state and complete audit trail.

### Phase 3: Enterprise Dashboard UI (Days 5–6 — Nov 25–27)
**Goal:** Visually distinctive, responsive SRE command center connected to live backend state.
- [ ] Design & implement dark obsidian/slate precision-telemetry theme (`TopBar` with scenario controls & AI mode toggle, `ExecutiveStrip` with Resilience Score, Active Incidents, Severity Distribution, Infrastructure Health).
- [ ] Build **Interactive Dependency Graph** (`@xyflow/react`) with custom `ServiceNodeCard` (live latency, error rate, status pulse), blast-radius highlighting, probable root-cause indicator, and animated failing edges.
- [ ] Build **Incident Investigation Panel** (root cause hypothesis, cited evidence list with event IDs, confidence bar, inference mode badge, explicit limitations).
- [ ] Build **AI Agent Activity Feed** showing live 6-agent progression and execution durations.
- [ ] Build **Recovery Operations Panel** (step-by-step allowlisted actions, Trust Policy verdict & matched rules, Approve/Reject actions, live Verification SLO checklist).
- [ ] Build **Audit Timeline** with actor-type filter (`SYSTEM`, `AGENT`, `POLICY`, `HUMAN`) and expandable details.
- **Exit Criteria:** Full demo can be run entirely from the browser with zero page reloads via SSE.

### Phase 4: Integration, Polish & Reproducibility (Days 7–8 — Nov 27–29)
**Goal:** Bulletproof demo experience and clean containerization.
- [ ] Tune propagation timings & recovery curves so the full demo flows smoothly in ~45–60 seconds.
- [ ] Test both `deterministic` mode (zero API key) and `llm` mode (with API key) plus forced fallback behavior.
- [ ] Add `backend/Dockerfile`, `frontend/Dockerfile` (with SSE-safe `nginx.conf`), and `docker-compose.yml`.
- [ ] Verify responsive layout across desktop (1440px, 1280px) and smaller viewports.
- [ ] Optional P2 stretch: Add a second scenario (`worker_memory_leak` or `payment_rate_limit`) if ahead of schedule.
- **Exit Criteria:** `docker compose up --build` starts cleanly from scratch and passes a full manual + automated demo run.

### Phase 5: Demo Script, Documentation & Submission Buffer (Day 9 — Nov 29–30)
**Goal:** Final verification and hackathon presentation readiness.
- [ ] Write concise root `README.md` with setup instructions, architecture diagram, and 3-minute judge walkthrough script.
- [ ] Run full pytest suite + frontend production build (`npm run build`).
- [ ] Rehearse end-to-end demo recording / live pitch flow; keep Day 9 afternoon as safety buffer for bug fixes only (no new features).

---

## Scope-Creep Guardrails

1. **No extra infrastructure containers** (no Postgres, Redis, Kafka, or Prometheus). SQLite + in-process asyncio simulator is sufficient and rock-solid.
2. **No auth/login flows** for the hackathon MVP; operator identity defaults to `"sre-operator"` (editable in the approval modal if desired).
3. **No unrequested pages or settings screens**; keep the experience focused on a cohesive single-workspace command center with clear drill-down drawers/panels.
4. **Freeze features on Day 8** so Day 9 is strictly verification, bug fixes, and submission polish.

