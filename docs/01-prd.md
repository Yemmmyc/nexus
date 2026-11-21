# NEXUS — Product Requirements Document (PRD)

**Project:** NEXUS — Autonomous Infrastructure Resilience & Trust Engine  
**Tagline:** *Predict. Investigate. Recover. Verify.*  
**Event:** BUILD 2036 Hackathon  
**Submission Deadline:** November 30, 2026  
**Document Status:** Draft v1.0 (MVP Specification)

---

## 1. Executive Summary

Modern distributed systems fail in cascades: a single degraded database can trigger API timeouts, payment failures, and message queue backlogs within seconds, flooding on-call engineers with dozens of disconnected alerts.

**NEXUS** is an AI-enabled infrastructure resilience platform that detects simulated infrastructure failures, correlates alert storms into unified incidents, performs evidence-backed root cause analysis, quantifies blast radius and risk, proposes safe remediation plans gated by explicit trust policies, executes controlled simulated recovery actions, and verifies service restoration—recording every decision in an immutable audit trail.

For BUILD 2036, NEXUS will be delivered as a **local, reproducible, zero-cloud-cost MVP** demonstrating an end-to-end autonomous-yet-governed incident lifecycle.

---

## 2. Goals & Non-Goals

### 2.1 MVP Goals (In Scope)
- **End-to-End Cascading Failure Demo:** Reliably simulate a multi-service cascading outage (`postgres-primary` latency spike -> API timeouts -> payment degradation -> order queue backlog) and drive it through detection, investigation, policy-gated approval, simulated remediation, and recovery verification.
- **Evidence-Based AI with Deterministic Fallback:** Use structured LLM reasoning grounded strictly in observed telemetry, events, and topology—with a zero-API-key deterministic mode so demos and tests never fail due to external API outages or rate limits.
- **Trust & Safety by Design:** Strictly separate recommendation from execution. Enforce declarative policy gates, allowlisted simulated playbooks (zero arbitrary shell execution), visible AI confidence/limitations, and a full audit trail.
- **Executive & SRE Dashboard:** Deliver a cohesive, responsive, visually distinctive enterprise command-center UI with an interactive dependency graph and live incident operations.
- **One-Command Reproducibility:** Run cleanly via `docker compose up --build` (and locally via Python/Node) with SQLite persistence.

### 2.2 Non-Goals (Out of Scope for Hackathon MVP)
- Real cloud infrastructure integration (AWS/GCP/Kubernetes) or live production telemetry ingestion.
- Execution of real infrastructure mutations, shell commands, or destructive operations.
- Multi-tenant RBAC, SSO/OAuth authentication, or external pager integrations (PagerDuty/Slack).
- Heavyweight distributed message brokers (Kafka/RabbitMQ) or external databases (Postgres/Redis) for NEXUS itself.
- Independent long-running LLM swarms for every agent role.

---

## 3. Target Users & Demo Persona

| Persona | Primary Need | Key NEXUS Interaction |
| :--- | :--- | :--- |
| **Site Reliability Engineer (SRE) / On-Call Operator** | Cut through alert noise, pinpoint root cause quickly, and execute safe recovery without making outages worse. | Inspects dependency graph, reviews AI root cause & evidence, approves/rejects policy-gated remediation, monitors verification. |
| **Engineering / Platform Leader** | Understand overall system resilience, blast radius, and governance compliance during high-severity incidents. | Monitors Executive Overview (Resilience Score, severity distribution, health) and reviews the immutable Audit Timeline. |
| **Hackathon Judge / Reviewer** | Experience a clear, believable, reproducible end-to-end story in 3–5 minutes. | Triggers the cascading failure scenario with one click, watches live correlation & investigation, approves remediation, and observes verified recovery. |

---

## 4. Core Capabilities & Functional Requirements

| ID | Capability | MVP Requirement | Priority |
| :--- | :--- | :--- | :--- |
| **FR-01** | **Infrastructure Simulator** | Simulate a 7-service fintech/checkout topology locally with realistic baseline metrics (latency, error rate, CPU, saturation, queue depth) and injectable fault scenarios. | P0 |
| **FR-02** | **Telemetry & Event Generation** | Emit periodic metric ticks (every 2s) and threshold-based monitoring events/alerts across affected services. | P0 |
| **FR-03** | **Incident Correlation** | Group temporally and topologically related alerts into a single `Incident` to eliminate alert fatigue. | P0 |
| **FR-04** | **Dependency Mapping** | Maintain a directed service dependency graph and compute upstream/downstream impact paths. | P0 |
| **FR-05** | **AI Investigation & RCA** | Analyze correlated events, telemetry deltas, and dependency topology to produce a probable root cause with cited evidence, confidence score (0–1), and explicit limitations. Support LLM + Deterministic modes. | P0 |
| **FR-06** | **Blast Radius & Risk Scoring** | Calculate affected services, customer-facing impact, severity (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`), and composite risk score (0–100). | P0 |
| **FR-07** | **Remediation Planning** | Generate an ordered `RemediationPlan` composed exclusively of parameterized actions from a predefined safe allowlist. | P0 |
| **FR-08** | **Safety & Policy Gate** | Evaluate every remediation plan against explicit rules (`AUTO_APPROVE`, `REQUIRE_HUMAN_APPROVAL`, `DENY`). High-risk or database-tier actions must require human approval. | P0 |
| **FR-09** | **Simulated Remediation Execution** | Execute approved allowlisted actions against the simulator state (never shell/OS commands) and log each step. | P0 |
| **FR-10** | **Recovery Verification** | Observe post-remediation telemetry over a verification window against explicit SLO thresholds; transition incident to `RESOLVED` or `VERIFICATION_FAILED`. | P0 |
| **FR-11** | **Incident Audit History** | Persist every system event, agent output, policy verdict, human decision, action execution, and verification result in SQLite. | P0 |
| **FR-12** | **Interactive Dashboard** | Present Executive Overview, Resilience Score, Active Incidents, Severity Distribution, Infrastructure Health, Interactive Dependency Graph, Investigation Panel, Agent Activity, Recovery Operations, and Audit Timeline. | P0 |
| **FR-13** | **Secondary Fault Scenario** | Support a second lightweight scenario (e.g., `payment_rate_limit_spike` or `worker_memory_leak`) to prove generality beyond a single hardcoded path. | P2 (Stretch) |

---

## 5. Required Demo Scenario: Cascading Database Latency Failure

1. **Healthy Baseline:** All 7 services (`api-gateway`, `auth-service`, `checkout-api`, `payment-service`, `order-queue`, `worker-fulfillment`, `postgres-primary`) report healthy metrics; Resilience Score is ~96–98.
2. **Fault Injection:** Operator triggers **Inject DB Latency Cascade**.
   - `postgres-primary`: Connection pool saturates (98%), query p99 latency spikes from ~18ms to >1,800ms.
   - `payment-service` & `checkout-api`: Upstream calls time out; error rates exceed 35%, p99 > 4,500ms.
   - `api-gateway`: Returns HTTP 504 gateway timeouts to clients.
   - `order-queue` & `worker-fulfillment`: Message backlog accumulates (>4,000 queued orders) as fulfillment writes stall on DB locks.
3. **Detection & Correlation (Observer Agent):** Multiple monitoring alerts across 5 services are correlated into one `CRITICAL` incident.
4. **Investigation (Investigator Agent):** Identifies `postgres-primary` connection pool saturation as the probable root cause (confidence ~0.88–0.94), citing specific metric spikes, alert timestamps, and upstream dependency order, while noting limitations (e.g., no live SQL query plan inspection in simulated telemetry).
5. **Risk Assessment (Risk Agent):** Computes blast radius (5 of 7 services affected, checkout & payments impacted) and risk score (~89/100).
6. **Remediation Planning (Recovery Agent):** Proposes a 3-step allowlisted plan:
   - `expand_db_connection_pool` on `postgres-primary`
   - `enable_circuit_breaker` on `payment-service`
   - `scale_queue_consumers` on `worker-fulfillment`
7. **Policy Gate (Trust Agent):** Flags plan as `REQUIRE_HUMAN_APPROVAL` because severity is `CRITICAL` and Step 1 modifies primary database capacity.
8. **Human Approval & Simulated Execution:** Operator reviews evidence and clicks **Approve & Execute**. Simulator applies the actions; metrics begin recovering over 6–10 seconds.
9. **Verification (Verification Agent):** Confirms DB latency < 100ms, API error rate < 1%, and queue depth draining; marks incident `RESOLVED` and restores Resilience Score.
10. **Audit Trail:** Full chronological record is inspectable and persists across page refreshes.

---

## 6. Security, Trust & Governance Requirements

- **No Real Execution:** Remediation handlers only mutate in-memory/SQLite simulation parameters. No `subprocess`, `os.system`, or dynamic code evaluation is permitted.
- **Strict Action Allowlist:** The Recovery Agent may only emit action IDs registered in the static `ACTION_CATALOG` with Pydantic-validated parameters.
- **Separation of Recommendation & Execution:** Agents can only create `PROPOSED` plans. Execution requires a `TrustPolicyVerdict` of `AUTO_APPROVE` or an explicit `POST /remediations/{plan_id}/approve` human action.
- **Evidence Grounding:** Every root cause hypothesis must link to concrete `event_id`s or `metric_snapshot` records. Uncited claims are disallowed by schema validation.
- **AI Transparency:** UI must display inference mode (`LLM` vs `Deterministic`), confidence score, supporting evidence, and explicit limitations/uncertainties.

---

## 7. Success Criteria for BUILD 2036

- **Functional Completeness:** Full cascading failure demo runs end-to-end in under 90 seconds from fault injection to verified recovery.
- **Zero-Failure Demo Reliability:** Deterministic fallback produces rich, coherent, evidence-backed results with zero external API keys required; optional LLM mode seamlessly enhances investigation prose when an API key is provided.
- **Visual & UX Quality:** Dashboard renders cleanly on desktop (1280px+) and tablet viewports without layout breakage, with smooth graph interactions and real-time updates.
- **Reproducibility:** Fresh clone + `docker compose up --build` starts backend and frontend cleanly with seeded topology and zero manual DB setup.

