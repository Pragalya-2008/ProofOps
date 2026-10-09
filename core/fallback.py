"""Deterministic Fallback Engine for proofOps.
Provides real, deterministic investigative workflows using the exact same safety gate,
tools, and hypothesis board when Gemini API key is absent, rate-limited, or failed.
"""
from typing import Any, Callable, Dict, List, Optional
from core.tools import execute_tool

def run_fallback_step(
    S: Dict[str, Any],
    sleep_fn: Optional[Callable[[float], None]] = None
) -> Dict[str, Any]:
    """Executes the next logical investigative or remedial step in fallback mode.
    Returns the step report.
    """
    phase = S.get("phase", "IDLE")
    if phase in ("RESOLVED", "ESCALATED", "AWAITING_APPROVAL"):
        return {"status": "paused_or_terminal", "phase": phase}

    incident = S.get("incident")
    if not incident:
        return {"status": "idle", "message": "No active incident to investigate"}

    scenario = incident.get("scenario")
    timeline = S.get("timeline", [])
    actions_taken = [t.get("text", "") for t in timeline]
    diag_calls = S.get("diag_calls", 0)

    # 1. First: Alert triage & topology check
    if not any("get_alert" in a for a in actions_taken):
        res = execute_tool(S, "get_alert", {}, sleep_fn=sleep_fn)
        S["diag_calls"] = diag_calls + 1
        return {"action": "get_alert", "result": res}

    if not any("get_topology" in a for a in actions_taken):
        res = execute_tool(S, "get_topology", {}, sleep_fn=sleep_fn)
        S["diag_calls"] = S.get("diag_calls", 0) + 1
        return {"action": "get_topology", "result": res}

    # 2. Service-specific telemetry gathering
    if scenario in ("cache_outage", "repeat_cache_outage"):
        if not any("ping_dependency" in a for a in actions_taken):
            res = execute_tool(S, "ping_dependency", {"from_service": "orders_api", "to_service": "cache"}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "ping_dependency", "result": res}

        if not any("find_similar_incident" in a for a in actions_taken):
            res = execute_tool(S, "find_similar_incident", {"signature": incident.get("signature", "")}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "find_similar_incident", "result": res}

        if not any("query_logs" in a for a in actions_taken):
            res = execute_tool(S, "query_logs", {"service": "cache", "minutes": 10}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "query_logs", "result": res}

        # Update hypotheses board
        if not S.get("hypotheses"):
            res = execute_tool(S, "update_hypotheses", {
                "hypotheses": [
                    {
                        "cause": "Redis Cache Process Outage",
                        "confidence": 0.95,
                        "status": "confirmed",
                        "evidence": "Ping orders_api -> cache returned connection refused; logs show SIGSEGV; worker backlog 380",
                    },
                    {
                        "cause": "PostgreSQL Database Connection Pool Exhaustion",
                        "confidence": 0.1,
                        "status": "eliminated",
                        "evidence": "Database health check passed, 18/100 active connections, integrity ok",
                    },
                    {
                        "cause": "Network Partition on API Gateway",
                        "confidence": 0.05,
                        "status": "eliminated",
                        "evidence": "API process listening, upstream timeouts originate strictly from redis",
                    },
                ]
            }, sleep_fn=sleep_fn)
            return {"action": "update_hypotheses", "result": res}

        # Remediation
        if not any("restart_cache" in a for a in actions_taken):
            res = execute_tool(S, "restart_cache", {}, sleep_fn=sleep_fn)
            return {"action": "restart_cache", "result": res}

        # Verification
        last_v = S.get("last_verification")
        if not last_v or last_v.get("status") != "passed":
            res = execute_tool(S, "verify_recovery", {}, sleep_fn=sleep_fn)
            return {"action": "verify_recovery", "result": res}

        # Resolution
        if S.get("phase") != "RESOLVED":
            res = execute_tool(S, "resolve_incident", {
                "summary": "Redis cache process crashed; restarted via reversible safety tier. Worker queue drained, latency normalized."
            }, sleep_fn=sleep_fn)
            return {"action": "resolve_incident", "result": res}

    elif scenario == "bad_config":
        if not any("diff_config" in a for a in actions_taken):
            res = execute_tool(S, "diff_config", {"service": "orders_api"}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "diff_config", "result": res}

        if not any("get_recent_deployments" in a for a in actions_taken):
            res = execute_tool(S, "get_recent_deployments", {}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "get_recent_deployments", "result": res}

        if not S.get("hypotheses"):
            res = execute_tool(S, "update_hypotheses", {
                "hypotheses": [
                    {
                        "cause": "Missing DATABASE_URL in Deployment v2.4.1",
                        "confidence": 0.98,
                        "status": "confirmed",
                        "evidence": "Config diff reveals DATABASE_URL missing in current env; deployment dep-892 deployed 12m ago; orders_api crashloop",
                    },
                    {
                        "cause": "External Network Routing Failure",
                        "confidence": 0.05,
                        "status": "eliminated",
                        "evidence": "Container crashes internally before binding port; internal crashloop backoff",
                    },
                ]
            }, sleep_fn=sleep_fn)
            return {"action": "update_hypotheses", "result": res}

        # Check if rollback has already been approved and executed
        is_rolled_back = (
            S.get("services", {}).get("orders_api", {}).get("version") == "v2.4.0"
            or any("rollback_config" in a and "approved" in a for a in actions_taken)
        )
        if is_rolled_back:
            # Already executed rollback, verify now
            last_v = S.get("last_verification")
            if not last_v or last_v.get("status") != "passed":
                res = execute_tool(S, "verify_recovery", {}, sleep_fn=sleep_fn)
                return {"action": "verify_recovery", "result": res}

            if S.get("phase") != "RESOLVED":
                res = execute_tool(S, "resolve_incident", {
                    "summary": "Configuration rollback to v2.4.0 restored DATABASE_URL. Readiness probes passed and error rate returned to 0.3%."
                }, sleep_fn=sleep_fn)
                return {"action": "resolve_incident", "result": res}

        # Otherwise trigger rollback (which will require approval)
        res = execute_tool(S, "rollback_config", {"service": "orders_api", "to_version": "v2.4.0"}, approved=False, sleep_fn=sleep_fn)
        return {"action": "rollback_config", "result": res}

    elif scenario == "database_integrity":
        if not any("ping_dependency" in a for a in actions_taken):
            res = execute_tool(S, "ping_dependency", {"from_service": "orders_api", "to_service": "database"}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "ping_dependency", "result": res}

        if not any("query_logs" in a for a in actions_taken):
            res = execute_tool(S, "query_logs", {"service": "database", "minutes": 15}, sleep_fn=sleep_fn)
            S["diag_calls"] = S.get("diag_calls", 0) + 1
            return {"action": "query_logs", "result": res}

        if not S.get("hypotheses"):
            res = execute_tool(S, "update_hypotheses", {
                "hypotheses": [
                    {
                        "cause": "Physical Database Table Checksum Mismatch / Corruption",
                        "confidence": 0.96,
                        "status": "confirmed",
                        "evidence": "Logs show 'CRITICAL checksum mismatch on orders table'; orders_api query aborts with SQLSTATE 58P01",
                    },
                    {
                        "cause": "Bad Application Code / Query Bug",
                        "confidence": 0.15,
                        "status": "eliminated",
                        "evidence": "Errors occur at database disk layer; no recent application deployment",
                    },
                ]
            }, sleep_fn=sleep_fn)
            return {"action": "update_hypotheses", "result": res}

        # Expose blocked repair tool to show safety gate enforcement
        if not any("repair_database" in a for a in actions_taken):
            res = execute_tool(S, "repair_database", {"service": "database"}, sleep_fn=sleep_fn)
            return {"action": "repair_database", "result": res}

        # Page human with Evidence Packet
        if S.get("phase") != "ESCALATED":
            res = execute_tool(S, "page_human", {
                "summary": "Database table 'orders' suffered critical checksum corruption on primary volume",
                "evidence": "Integrity validation FAILED_CHECKSUM_ERROR; 22% orders_api transaction failures; repair_database blocked by safety gate",
                "recommended_next_step": "Isolate database instance, activate read-only replica, and restore orders table from verified snapshot snapshot-20261009-001",
            }, sleep_fn=sleep_fn)
            return {"action": "page_human", "result": res}

    return {"status": "idle", "message": "No further steps pending"}
