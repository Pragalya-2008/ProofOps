"""End-to-end tests for all 4 demo scenarios."""
import pytest
from core.state import create_initial_state, reset_environment
from core.faults import inject_fault
from core.agent import run_investigation_until_pause, run_agent_turn, MODEL_NAME
from core.tools import execute_tool

def test_model_name_constant():
    assert MODEL_NAME is not None
    assert "gemini" in MODEL_NAME.lower()

def test_scenario_1_cache_outage_auto_healed():
    S = create_initial_state()
    inject_fault(S, "cache_outage")
    assert S["phase"] == "INVESTIGATING"

    # Run agent loop until completion (using fast no-op sleep)
    res = run_investigation_until_pause(S, api_key="", sleep_fn=lambda _: None)

    assert S["phase"] == "RESOLVED"
    assert S["services"]["cache"]["reachable"] is True
    assert S["services"]["orders_api"]["healthy"] is True
    assert S["services"]["worker"]["queue_depth"] < 20
    assert len(S["hypotheses"]) >= 2
    # Verify postmortem saved to memory
    assert len(S["memory"]) == 1
    assert S["memory"][0]["scenario"] == "cache_outage"

def test_scenario_2_repeat_cache_outage_with_memory():
    S = create_initial_state()
    # First incident
    inject_fault(S, "cache_outage")
    run_investigation_until_pause(S, api_key="", sleep_fn=lambda _: None)
    assert len(S["memory"]) == 1

    # Reset environment (preserves memory)
    reset_environment(S)
    assert S["phase"] == "IDLE"
    assert len(S["memory"]) == 1

    # Inject repeat cache outage
    inject_fault(S, "repeat_cache_outage")
    run_investigation_until_pause(S, api_key="", sleep_fn=lambda _: None)

    assert S["phase"] == "RESOLVED"
    # Second postmortem added to memory
    assert len(S["memory"]) == 2

def test_scenario_3_bad_config_approval_gate():
    S = create_initial_state()
    inject_fault(S, "bad_config")
    assert S["phase"] == "INVESTIGATING"

    # Run until pause -> should pause at AWAITING_APPROVAL
    res = run_investigation_until_pause(S, api_key="", sleep_fn=lambda _: None)
    assert S["phase"] == "AWAITING_APPROVAL"
    assert S["pending"] is not None
    assert S["pending"]["tool"] == "rollback_config"

    # Human approves the pending action
    pending_tool = S["pending"]["tool"]
    pending_args = S["pending"]["args"]
    app_res = execute_tool(S, pending_tool, pending_args, approved=True, sleep_fn=lambda _: None)
    assert app_res["status"] == "success"

    # Resume investigation to verify and resolve
    res_after = run_investigation_until_pause(S, api_key="", sleep_fn=lambda _: None)
    assert S["phase"] == "RESOLVED"
    assert S["services"]["orders_api"]["healthy"] is True

def test_scenario_4_database_integrity_blocked_and_escalated():
    S = create_initial_state()
    inject_fault(S, "database_integrity")
    assert S["phase"] == "INVESTIGATING"

    # Run agent loop
    res = run_investigation_until_pause(S, api_key="", sleep_fn=lambda _: None)
    assert S["phase"] == "ESCALATED"

    # Verify blocked repair was logged
    timeline_texts = [t["text"] for t in S["timeline"]]
    assert any("BLOCKED" in t for t in timeline_texts)

    # Verify escalation packet
    assert "escalation_packet" in S
    packet = S["escalation_packet"]
    assert packet["incident_id"] == "inc-2026-104"
    assert "snapshot" in packet["recommended_next_step"]
