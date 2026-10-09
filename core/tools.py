"""Tool declarations and execution dispatcher for proofOps.
Exposes Gemini function declarations with strict JSON schemas and handles
code-level safety gating, timeline logging, and state transitions.
"""
from typing import Any, Callable, Dict, List, Optional
from core.state import add_timeline_entry
from core.sandbox import (
    get_topology,
    ping_dependency,
    check_health,
    get_metrics,
    query_logs,
    diff_config,
    get_recent_deployments,
)
from core.faults import apply_restart_cache, apply_rollback_config
from core.verifier import verify_recovery as run_verify_recovery
from core.escalation import dispatch_escalation
from core.memory import find_similar_incident, save_postmortem
from core.guardrails import enforce_safety_gate, get_tool_tier

# Gemini Function Declarations for google-genai SDK
TOOL_DECLARATIONS = [
    {
        "name": "get_alert",
        "description": "Retrieves the active alert trigger, incident ID, severity, and incident signature.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "get_topology",
        "description": "Retrieves the microservice architecture graph including all services and dependencies.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "query_logs",
        "description": "Queries recent structured log lines for a specific service.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "Target service name: 'orders_api', 'worker', 'cache', or 'database'",
                },
                "minutes": {
                    "type": "INTEGER",
                    "description": "Log window duration in minutes (default 15)",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "get_metrics",
        "description": "Retrieves key operational metrics (latency, error rate, cpu, memory, queue, etc.) for a service.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "Service name to fetch metrics for: 'orders_api', 'worker', 'cache', or 'database'",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "check_health",
        "description": "Checks health status, liveness/readiness probes, and subsystem integrity for a service.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "Service name to check: 'orders_api', 'worker', 'cache', or 'database'",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "ping_dependency",
        "description": "Tests connectivity and protocol handshake between two interdependent services.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "from_service": {
                    "type": "STRING",
                    "description": "Source service originating the request (e.g. 'orders_api', 'worker')",
                },
                "to_service": {
                    "type": "STRING",
                    "description": "Target dependency service (e.g. 'cache', 'database', 'worker')",
                },
            },
            "required": ["from_service", "to_service"],
        },
    },
    {
        "name": "diff_config",
        "description": "Inspects environment variables and configuration diff between current and previous deployments.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "Service name to inspect config for (default 'orders_api')",
                },
            },
        },
    },
    {
        "name": "get_recent_deployments",
        "description": "Retrieves the deployment audit log including recent releases, versions, timestamps, and commit authors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "find_similar_incident",
        "description": "Searches organizational incident memory for historical postmortems matching the given signature or symptoms.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "signature": {
                    "type": "STRING",
                    "description": "Error signature or key diagnostic tokens to search for",
                },
            },
            "required": ["signature"],
        },
    },
    {
        "name": "update_hypotheses",
        "description": "Updates the visible Competing Root-Cause Hypotheses board. Keep 2-3 competing hypotheses active with confidence and status.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "hypotheses": {
                    "type": "ARRAY",
                    "description": "List of 2-3 root-cause hypotheses with evidence and status",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "cause": {
                                "type": "STRING",
                                "description": "Candidate root-cause hypothesis",
                            },
                            "confidence": {
                                "type": "NUMBER",
                                "description": "Confidence score between 0.0 and 1.0",
                            },
                            "status": {
                                "type": "STRING",
                                "description": "Status: 'open', 'eliminated', or 'confirmed'",
                            },
                            "evidence": {
                                "type": "STRING",
                                "description": "Concrete evidence supporting or eliminating this hypothesis",
                            },
                        },
                        "required": ["cause", "confidence", "status", "evidence"],
                    },
                },
            },
            "required": ["hypotheses"],
        },
    },
    {
        "name": "restart_cache",
        "description": "Reversible remediation: Restarts the Redis cache process and unblocks dependent queues.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "rollback_config",
        "description": "Human-approved remediation: Rolls back configuration changes and restores the previous known-good deployment environment.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "Service to roll back (e.g. 'orders_api')",
                },
                "to_version": {
                    "type": "STRING",
                    "description": "Target version tag to restore (e.g. 'v2.4.0')",
                },
            },
            "required": ["service", "to_version"],
        },
    },
    {
        "name": "repair_database",
        "description": "Attempts automated direct repair and checksum rewrite on primary database tables (BLOCKED in production).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "Database service name",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "verify_recovery",
        "description": "Runs 3 consecutive system-wide invariant checks to verify full operational recovery before incident resolution.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "page_human",
        "description": "Escalates the incident to the human on-call engineer with a detailed Evidence Packet when safety gate prohibits action or manual intervention is needed.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "summary": {
                    "type": "STRING",
                    "description": "High-level summary of the incident and current system status",
                },
                "evidence": {
                    "type": "STRING",
                    "description": "Key telemetry, logs, and findings gathered during investigation",
                },
                "recommended_next_step": {
                    "type": "STRING",
                    "description": "Actionable next steps recommended for the human responder",
                },
            },
            "required": ["summary", "evidence", "recommended_next_step"],
        },
    },
    {
        "name": "resolve_incident",
        "description": "Closes the incident and triggers automated postmortem recording. Only accepted if verify_recovery has previously PASSED.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "summary": {
                    "type": "STRING",
                    "description": "Final root-cause and resolution summary for the postmortem",
                },
            },
            "required": ["summary"],
        },
    },
]

def execute_tool(
    S: Dict[str, Any],
    name: str,
    args: Optional[Dict[str, Any]] = None,
    approved: bool = False,
    sleep_fn: Optional[Callable[[float], None]] = None
) -> Dict[str, Any]:
    """Central tool execution gateway with code safety gate enforcement and timeline logging."""
    args = args or {}
    tier = get_tool_tier(name)
    gate_decision = enforce_safety_gate(name, args, approved=approved)

    # 1. Blocked execution
    if gate_decision["status"] == "blocked":
        add_timeline_entry(
            S,
            actor="agent",
            kind="action",
            text=f"Attempted tool '{name}' -> BLOCKED by safety policy.",
            tier="blocked",
        )
        return {
            "status": "blocked",
            "message": "Blocked by safety policy.",
            "details": gate_decision["message"],
        }

    # 2. Approval required
    if gate_decision["status"] == "approval_required":
        S["pending"] = {
            "tool": name,
            "args": args,
            "reason": gate_decision["message"],
            "risk": "High-impact production change",
        }
        S["phase"] = "AWAITING_APPROVAL"

        add_timeline_entry(
            S,
            actor="agent",
            kind="approval",
            text=f"Requested approval for '{name}' with args {args}.",
            tier="approval",
        )
        return {
            "status": "approval_required",
            "tool": name,
            "args": args,
            "message": gate_decision["message"],
        }

    # 3. Permitted execution (read, reversible, or approved approval)
    approval_suffix = " (approved by human operator)" if (approved and tier == "approval") else ""
    add_timeline_entry(
        S,
        actor="human" if (approved and tier == "approval") else "agent",
        kind="action" if tier in ("reversible", "approval") else "check",
        text=f"Invoked tool '{name}'{approval_suffix} (args: {args})",
        tier=tier,
    )

    # Execute actual tool logic
    try:
        if name == "get_alert":
            inc = S.get("incident")
            return inc if inc else {"alert": "No active incident", "status": "nominal"}

        elif name == "get_topology":
            return get_topology()

        elif name == "query_logs":
            svc = args.get("service", "orders_api")
            mins = int(args.get("minutes", 15))
            return query_logs(S, service=svc, minutes=mins)

        elif name == "get_metrics":
            svc = args.get("service", "orders_api")
            return get_metrics(S, service=svc)

        elif name == "check_health":
            svc = args.get("service", "orders_api")
            return check_health(S, service=svc)

        elif name == "ping_dependency":
            from_svc = args.get("from_service", "orders_api")
            to_svc = args.get("to_service", "cache")
            return ping_dependency(S, from_service=from_svc, to_service=to_svc)

        elif name == "diff_config":
            svc = args.get("service", "orders_api")
            return diff_config(S, service=svc)

        elif name == "get_recent_deployments":
            return get_recent_deployments(S)

        elif name == "find_similar_incident":
            sig = args.get("signature", "")
            return find_similar_incident(S, signature=sig)

        elif name == "update_hypotheses":
            hyps = args.get("hypotheses", [])
            S["hypotheses"] = hyps
            add_timeline_entry(
                S,
                actor="agent",
                kind="hypothesis",
                text=f"Updated hypotheses board ({len(hyps)} candidate causes).",
                tier="read",
            )
            return {
                "status": "updated",
                "count": len(hyps),
                "hypotheses": hyps,
            }

        elif name == "restart_cache":
            S["phase"] = "REMEDIATING"
            res = apply_restart_cache(S)
            return res

        elif name == "rollback_config":
            S["phase"] = "REMEDIATING"
            svc = args.get("service", "orders_api")
            ver = args.get("to_version", "v2.4.0")
            res = apply_rollback_config(S, service=svc, to_version=ver)
            S["pending"] = None
            return res

        elif name == "repair_database":
            # Expose to model so safety gate handles it; fallback if gate permitted
            return {"status": "blocked", "message": "Blocked by safety policy."}

        elif name == "verify_recovery":
            S["phase"] = "VERIFYING"
            v_res = run_verify_recovery(S, sleep_fn=sleep_fn)
            S["last_verification"] = v_res
            add_timeline_entry(
                S,
                actor="system",
                kind="verification",
                text=f"Verification status: {v_res['status'].upper()} ({v_res['consecutive_passes']}/{v_res['required_passes']} passes).",
                tier="read",
            )
            return v_res

        elif name == "page_human":
            summary = args.get("summary", "Incident requires human intervention")
            evidence = args.get("evidence", "Telemetry collected in state")
            next_step = args.get("recommended_next_step", "Inspect cluster manually")
            return dispatch_escalation(
                S,
                summary=summary,
                evidence=evidence,
                recommended_next_step=next_step,
            )

        elif name == "resolve_incident":
            summary = args.get("summary", "Incident resolved successfully")
            last_v = S.get("last_verification")
            if not last_v or last_v.get("status") != "passed":
                return {
                    "status": "rejected",
                    "message": "Cannot resolve incident: verify_recovery has not passed 3 consecutive invariant checks.",
                }

            S["phase"] = "RESOLVED"
            postmortem = save_postmortem(S, summary=summary)
            add_timeline_entry(
                S,
                actor="agent",
                kind="resolution",
                text=f"Incident RESOLVED: {summary}. Automated postmortem saved to memory.",
                tier="read",
            )
            return {
                "status": "resolved",
                "message": "Incident successfully resolved and postmortem saved.",
                "postmortem": postmortem,
            }

        else:
            return {
                "status": "error",
                "message": f"Tool '{name}' is not recognized.",
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}
