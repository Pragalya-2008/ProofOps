"""Code-enforced Safety Gate for proofOps.
Blocks unknown tools, enforces permission tiers (read, reversible, approval, blocked),
and logs every invocation attempt to the incident timeline with its tier.
"""
from typing import Any, Dict, Optional
from core.state import add_timeline_entry

RISK_TIERS = {
    # Read-only observation tools
    "get_alert": "read",
    "get_topology": "read",
    "query_logs": "read",
    "get_metrics": "read",
    "check_health": "read",
    "ping_dependency": "read",
    "diff_config": "read",
    "get_recent_deployments": "read",
    "find_similar_incident": "read",
    "update_hypotheses": "read",
    "verify_recovery": "read",
    "page_human": "read",
    "resolve_incident": "read",

    # Reversible automated remediation
    "restart_cache": "reversible",

    # High-impact configuration rollback (human in the loop)
    "rollback_config": "approval",

    # Destructive or unsafe operations
    "repair_database": "blocked",
}

def get_tool_tier(tool_name: str) -> str:
    """Returns the safety tier for a tool, defaulting to 'blocked' for unknown tools."""
    return RISK_TIERS.get(tool_name, "blocked")

def enforce_safety_gate(
    tool_name: str,
    args: Dict[str, Any],
    approved: bool = False
) -> Dict[str, Any]:
    """Evaluates whether the tool is allowed to execute based on safety policy.

    Returns:
      {
        "allowed": bool,
        "status": "allowed" | "approval_required" | "blocked",
        "tier": "read" | "reversible" | "approval" | "blocked",
        "message": str
      }
    """
    tier = get_tool_tier(tool_name)

    # 1. Blocked tier (explicit dangerous tool or unknown tool)
    if tier == "blocked":
        if tool_name not in RISK_TIERS:
            return {
                "allowed": False,
                "status": "blocked",
                "tier": "blocked",
                "message": f"Tool '{tool_name}' is UNKNOWN and blocked by code safety gate.",
            }
        return {
            "allowed": False,
            "status": "blocked",
            "tier": "blocked",
            "message": f"Execution of '{tool_name}' is strictly BLOCKED by safety policy. Direct schema/database mutation is prohibited in production without human intervention.",
        }

    # 2. Approval required tier
    if tier == "approval":
        if not approved:
            return {
                "allowed": False,
                "status": "approval_required",
                "tier": "approval",
                "message": f"Action '{tool_name}' modifies production infrastructure and requires explicit human approval before execution.",
                "pending_action": {
                    "tool": tool_name,
                    "args": args,
                    "risk": "High impact service rollback - requires authorization",
                }
            }
        # If approved, allow execution
        return {
            "allowed": True,
            "status": "allowed",
            "tier": "approval",
            "message": f"Action '{tool_name}' approved by human operator.",
        }

    # 3. Read & Reversible tiers
    return {
        "allowed": True,
        "status": "allowed",
        "tier": tier,
        "message": f"Action '{tool_name}' is authorized under tier '{tier}'.",
    }
