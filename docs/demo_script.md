# proofOps Demo Script (CTRL+AI Challenge, PS-12 Auto-Heal)

## Executive Summary
**proofOps** is an evidence-first autonomous incident-response agent for microservice platforms.
Unlike naive LLM scripts that guess fixes or hallucinate root causes, proofOps enforces:
1. **Read-Only First Investigation**: strictly observes telemetry, logs, and dependencies prior to proposing action.
2. **Competing Root-Cause Hypotheses Board**: tracks 2–3 competing hypotheses with confidence percentages and concrete evidence.
3. **Code-Enforced Safety Gate**: safety rules are executed in Python code, not prompt hints. High-risk actions require human approval; unsafe operations (e.g., direct DB table mutation) are blocked.
4. **Multi-Point Recovery Verification**: requires 3 consecutive cycles (across 6 invariants) before an incident can be marked resolved.
5. **Organizational Memory**: persists postmortems so recurring incidents are diagnosed and resolved faster.
6. **Escalation Protocol**: when an auto-fix is prohibited or unsafe, compiles a complete Evidence Packet and pages the human on-call.

---

## Architecture & Services
Simulated orders platform with 4 interdependent services:
- `orders_api`: HTTP order gateway (depends on cache, database, worker)
- `worker`: Asynchronous background queue processor (depends on cache)
- `cache`: Redis cluster for session & rate limiting
- `database`: PostgreSQL primary transactional store

---

## Step-by-Step Demo Scenarios

### Scenario 1: Cache Outage (Auto-Healed)
1. **Inject Fault**:
   - In the sidebar, select **"1. Cache Outage (Auto-Healed)"** and click **"🔥 Inject Fault & Trigger Alert"**.
   - **Observable State**:
     - `orders_api` drops to 48% error rate, 2400ms latency.
     - `cache` shows `CONNECTION_REFUSED`.
     - `worker` queue surges from 4 to 380 unacknowledged jobs.
     - Live topology lines turn red/dashed.
2. **Run Autonomous Agent**:
   - Click **"▶ Auto-Run"** (or click **"Step Agent"** to observe each tool call).
   - **Observed Flow**:
     - Agent investigates `get_alert`, `get_topology`, `ping_dependency`, `query_logs`.
     - Populates Competing Hypotheses Board (Redis outage vs DB pool exhaustion vs Gateway partition).
     - Identifies Redis outage as confirmed (95% confidence).
     - Calls reversible remediation: `restart_cache`.
     - Executes `verify_recovery` (3 consecutive invariant checks pass).
     - Closes incident via `resolve_incident`.
   - **Postmortem**:
     - Automated postmortem is saved to Organizational Memory.

---

### Scenario 2: Repeat Cache Outage (Memory-Accelerated)
1. **Inject Fault**:
   - Click **"🔄 Reset Environment"** (preserves organizational memory and past postmortems).
   - Select **"2. Repeat Cache Outage (Memory Accelerated)"** and click **"🔥 Inject Fault"**.
2. **Run Autonomous Agent**:
   - Click **"▶ Auto-Run"**.
   - **Observed Flow**:
     - Agent queries `find_similar_incident` with error signature.
     - Discovers the previous postmortem from Scenario 1 in memory.
     - Immediately converges on the root cause and restarts the cache.
     - Verification passes and MTTR is significantly reduced.

---

### Scenario 3: Bad Config (Rollback Needs Human Approval)
1. **Inject Fault**:
   - Click **"🔄 Reset Environment"**.
   - Select **"3. Bad Config (Rollback Needs Human Approval)"** and click **"🔥 Inject Fault"**.
   - **Observable State**:
     - Deployment `v2.4.1` deployed 12 minutes ago.
     - `orders_api` crashes with 100% errors (crashloop).
2. **Run Investigation**:
   - Click **"▶ Auto-Run"**.
   - **Observed Flow**:
     - Agent inspects `diff_config(orders_api)` and `get_recent_deployments`.
     - Detects `DATABASE_URL` was removed in `v2.4.1`.
     - Formulates hypothesis: "Missing DATABASE_URL in Deployment v2.4.1" (98% confidence).
     - Attempts `rollback_config(service='orders_api', to_version='v2.4.0')`.
     - **Safety Gate Intervention**: Code policy catches `rollback_config` under the **APPROVAL** tier.
     - Agent pauses; phase transitions to **`AWAITING_APPROVAL`**.
3. **Human in the Loop**:
   - The UI displays the pending action with reasons and risk.
   - Click **"✅ Approve"** in the sidebar.
   - The tool executes, config is restored to `v2.4.0`, verification passes, and incident is resolved.

---

### Scenario 4: Database Integrity Fault (Repair Blocked, Human Paged)
1. **Inject Fault**:
   - Click **"🔄 Reset Environment"**.
   - Select **"4. DB Integrity Fault (Repair Blocked, Paged)"** and click **"🔥 Inject Fault"**.
   - **Observable State**:
     - `database` integrity check fails: `CRITICAL checksum mismatch on orders table`.
     - `orders_api` errors spike to 22%.
2. **Run Investigation**:
   - Click **"▶ Auto-Run"**.
   - **Observed Flow**:
     - Agent inspects `ping_dependency` and `query_logs(database)`.
     - Hypotheses board flags table checksum corruption.
     - Agent attempts `repair_database(database)`.
     - **Safety Gate Enforcement**: `repair_database` is strictly **BLOCKED** by policy (direct DB table mutations prohibited in production).
     - Agent recognizes that it cannot safely auto-heal the incident.
     - Calls `page_human` with summary, forensic evidence, and recommended snapshot restore.
     - Phase transitions to **`ESCALATED`**.
   - **Evidence Packet**:
     - Forensic Evidence Packet is generated and displayed on screen for the on-call engineer.

---

## Running the Automated Test Suite
Run all unit and end-to-end scenario tests:
```bash
python3 -m pytest tests/ -v
```
All 16 tests will run and pass in ~7 seconds without requiring a browser or mock workarounds.
