# NEXUS — Three-Minute Competition Demo Script

**Competition:** BUILD 2036 — Digital Infrastructure (DPI · Cybersecurity · Cloud · Trust)  
**Target Duration:** 3 minutes (180 seconds)  
**Pre-Demo Setup:**
1. Run `docker compose up -d --build --wait` and confirm both containers are `healthy`.
2. Open `http://localhost:5173` at `1440×900` in Chrome.
3. Click **Reset Baseline** on **Overview** so the system starts cleanly at `Tick 0`, `7/7 Healthy`, `Resilience Score: 100.0`.

---

## Timed Walkthrough

### 0:00 – 0:20 | 1. Introduction & Problem Statement (Overview Tab)
- **Screen:** **Overview** (`http://localhost:5173`), showing `API: ONLINE`, `SQLite: READY`, `AI: DETERMINISTIC`, `7/7` healthy services, and `Resilience Score: 100.0`.
- **Talking Points:**
  - *"Digital public infrastructure and payment platforms fail in cascades—a single database bottleneck triggers API timeouts, checkout failures, and queue backlogs within seconds."*
  - *"NEXUS is an autonomous infrastructure resilience and trust engine built around four principles: **Predict. Investigate. Recover. Verify.** Everything you will see runs locally inside a deterministic simulator—no real payment processing or production infrastructure is modified."*

### 0:20 – 0:45 | 2. Inject Cascading Failure (Topology Tab)
- **Action:** Click **Topology** in the sidebar. Show the 7-service, 8-edge interactive graph (`7 Healthy`, `NO ACTIVE ROOT FAULT`).
- **Action:** Click **Inject `db_latency_cascade`**, then click **+1 Tick** six times (or click **Start** for ~12s and then **Stop**).
- **Talking Points:**
  - *"We inject a database connection pool saturation fault into `postgres-primary`. Rather than hardcoding outcomes, NEXUS propagates latency, errors, saturation, and queue conservation-of-flow mathematically across the dependency graph."*

### 0:45 – 1:10 | 3. Detection, Root Cause & Blast Radius (Topology Tab)
- **Screen:** Live `@xyflow/react` graph with `postgres-primary` highlighted as `ROOT CAUSE · CRITICAL` (`~1556ms`), 5 downstream services marked `IMPACTED`, `order-queue` backlog at `1316` messages, 7 animated failing edges, and `auth-service` calm and `HEALTHY` (`~17.6ms`, static edge).
- **Action:** Click `postgres-primary` to open the **Service Inspector** briefly, then click `auth-service` to show isolation.
- **Talking Points:**
  - *"Within seconds, an operator sees that `postgres-primary` is the origin, 5 dependent services are in the blast radius, `order-queue` has accumulated over 1,300 pending orders, and `auth-service` is completely unaffected."*

### 1:10 – 1:35 | 4. Evidence-Grounded Investigation (Incidents Tab)
- **Action:** Click **Incidents** in the sidebar → select `INC-0001` → click **Run Investigation**.
- **Screen:** **Incident Intelligence Dossier** populates with `Observer` → `Investigator` → `Risk Analyst` trace.
- **Talking Points:**
  - *"NEXUS runs three logical agents—Observer, Investigator, and Risk Analyst—completely functional in deterministic mode without requiring an external LLM, while supporting an optional evidence-grounded LLM adapter."*
  - *"Notice every finding cites traceable `EVID-*` records, classifies services into probable root cause, contributing cause, and downstream symptoms, calculates a transparent 4-criterion confidence score, and explicitly states analytical limitations."*

### 1:35 – 2:00 | 5. Recovery Plan & Trust Agent Policy Gate (Incidents Tab)
- **Action:** Scroll to **Policy-Gated Recovery Operations** → click **Propose Recovery Plan**.
- **Screen:** `PLAN-0001` (`expand_db_connection_pool` on `postgres-primary`) appears with `POLICY: REQUIRE_HUMAN_APPROVAL` and matched rules `POL-006` (database tier / high risk) and `POL-007` (`CRITICAL` severity).
- **Talking Points:**
  - *"The Recovery Agent can only select from a static allowlist of safe simulated actions—never arbitrary shell commands. It cannot execute directly. The independent Trust Agent evaluates declarative rules and enforces **Human Authorization Required** because this action touches the primary database during a critical incident."*

### 2:00 – 2:20 | 6. Human Approval & Controlled Simulated Execution (Incidents Tab)
- **Action:** Enter an operator note (e.g., *"Confirmed DB pool saturation from telemetry evidence"*), click **Approve Plan**, then click **Execute Simulated Recovery**.
- **Screen:** `Approval: APPROVED`, `Execution: COMPLETED` (`sim.exec.expand_db_connection_pool`), `Verification: IN_PROGRESS`.
- **Talking Points:**
  - *"Only after explicit operator approval does the executor unlock and apply the modeled mitigation to the local simulator. Notice the incident is still **not** marked resolved—NEXUS never assumes a remediation worked."*

### 2:20 – 2:45 | 7. Multi-Tick Verification & Resolution (Incidents → Topology → Audit Trail)
- **Action:** Click **Advance +2 Ticks & Verify** three times until `Verification` transitions from `IN_PROGRESS` (`0/2` → `1/2`) to **`VERIFIED` (`2/2` consecutive healthy ticks)** and `INC-0001` becomes **`RESOLVED`** (`Resilience Score: ~99.8`).
- **Action:** Click **Audit Trail** in the sidebar; filter to `INC-0001` and expand one payload (`Inspect payload`).
- **Talking Points:**
  - *"The Verification Agent monitors real post-remediation telemetry across consecutive ticks until database latency, downstream error rates, and queue depth all stabilize within SLO. Only then is the incident resolved. Every single step—detection, investigation, policy verdict, human approval, execution, and verification—is preserved in an append-only SQLite audit ledger."*

### 2:45 – 3:00 | 8. Closing Value Proposition
- **Screen:** **Audit Trail** showing all 6 recorded lifecycle milestones (`Detected` → `Investigated` → `Plan Proposed` → `Policy / Approval` → `Simulated Exec` → `Verified & Resolved`).
- **Talking Points:**
  - *"For Digital Public Infrastructure, speed without governance is dangerous, and governance without visibility is too slow. NEXUS proves that autonomous resilience can be deterministic, evidence-grounded, policy-enforced, and fully auditable—predicting, investigating, recovering, and verifying trust end to end."*
