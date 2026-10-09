"""Tests for tools, guardrails, and escalation."""
import pytest
from core.state import create_initial_state
from core.faults import inject_fault
from core.tools import execute_tool, TOOL_DECLARATIONS
from core.guardrails import enforce_safety_gate, get_tool_tier

def test_tool_declarations_count_and_schema():
    assert len(TOOL_DECLARATIONS) >= 14
    tool_names = [t["name"] for t in TOOL_DECLARATIONS]
    assert "get_alert" in tool_names
    assert "get_topology" in tool_names
    assert "restart_cache" in tool_names
    assert "rollback_config" in tool_names
    assert "repair_database" in tool_names
    assert "verify_recovery" in tool_names
    assert "page_human" in tool_names
    assert "resolve_incident" in tool_names

def test_safety_gate_blocked_tools():
    # repair_database is blocked
    res = enforce_safety_gate("repair_database", {})
    assert res["status"] == "blocked"
    assert res["tier"] == "blocked"

    # unknown tool is blocked
    res_unk = enforce_safety_gate("drop_database", {})
    assert res_unk["status"] == "blocked"

    S = create_initial_state()
    exec_res = execute_tool(S, "repair_database", {})
    assert exec_res["status"] == "blocked"

    exec_unk = execute_tool(S, "delete_cluster", {})
    assert exec_unk["status"] == "blocked"

def test_safety_gate_approval_flow():
    S = create_initial_state()
    inject_fault(S, "bad_config")

    # Call rollback_config without approval
    res = execute_tool(S, "rollback_config", {"service": "orders_api", "to_version": "v2.4.0"}, approved=False)
    assert res["status"] == "approval_required"
    assert S["phase"] == "AWAITING_APPROVAL"
    assert S["pending"]["tool"] == "rollback_config"

    # Now call with approved=True
    res_app = execute_tool(S, "rollback_config", {"service": "orders_api", "to_version": "v2.4.0"}, approved=True)
    assert res_app["status"] == "success"
    assert S["pending"] is None
    assert S["services"]["orders_api"]["healthy"] is True

def test_resolve_incident_requires_passing_verification():
    S = create_initial_state()
    inject_fault(S, "cache_outage")

    # Try resolving without verification -> should be rejected
    res = execute_tool(S, "resolve_incident", {"summary": "Fixed cache"})
    assert res["status"] == "rejected"
    assert S["phase"] != "RESOLVED"

    # Restart cache
    execute_tool(S, "restart_cache", {})

    # Run verification
    v_res = execute_tool(S, "verify_recovery", {}, sleep_fn=lambda _: None)
    assert v_res["status"] == "passed"

    # Now resolve incident
    res2 = execute_tool(S, "resolve_incident", {"summary": "Cache restarted, queue drained."})
    assert res2["status"] == "resolved"
    assert S["phase"] == "RESOLVED"
    assert len(S["memory"]) == 1
    assert S["memory"][0]["summary"] == "Cache restarted, queue drained."

def test_page_human_escalation_evidence_packet():
    S = create_initial_state()
    inject_fault(S, "database_integrity")

    # Update hypotheses
    execute_tool(S, "update_hypotheses", {
        "hypotheses": [
            {"cause": "Storage corruption on DB", "confidence": 0.95, "status": "confirmed", "evidence": "Checksum failed"},
            {"cause": "Bad deploy", "confidence": 0.1, "status": "eliminated", "evidence": "No recent deploy"},
        ]
    })

    # Page human
    res = execute_tool(S, "page_human", {
        "summary": "Database table orders failed integrity checksum",
        "evidence": "Logs show relation inconsistent; repair_database blocked",
        "recommended_next_step": "Restore database from snapshot snapshot-20261009-001",
    })

    assert res["status"] == "escalated"
    assert S["phase"] == "ESCALATED"
    packet = res["packet"]
    assert packet["incident_id"] == "inc-2026-104"
    assert len(packet["hypotheses_board"]) == 2
    assert "snapshot" in packet["recommended_next_step"]
