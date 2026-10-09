"""Tests for state, sandbox, faults, and verifier."""
import pytest
from core.state import create_initial_state, reset_environment
from core.sandbox import (
    get_topology,
    ping_dependency,
    check_health,
    get_metrics,
    query_logs,
    diff_config,
)
from core.faults import (
    inject_fault,
    apply_restart_cache,
    apply_rollback_config,
    SCENARIOS,
)
from core.verifier import evaluate_single_check, verify_recovery

def test_initial_state_baseline():
    S = create_initial_state()
    assert S["phase"] == "IDLE"
    assert S["services"]["orders_api"]["error_rate"] == 0.003
    assert S["services"]["orders_api"]["latency_ms"] == 120
    assert S["services"]["worker"]["queue_depth"] == 4
    assert S["services"]["cache"]["reachable"] is True
    assert S["services"]["database"]["integrity_ok"] is True
    assert S["services"]["database"]["connections"] == 18

def test_reset_environment_preserves_memory():
    S = create_initial_state()
    S["memory"].append({"id": "inc-old", "summary": "test incident"})
    S["llm_calls"] = 7
    S["phase"] = "REMEDIATING"

    reset_environment(S)
    assert S["phase"] == "IDLE"
    assert len(S["memory"]) == 1
    assert S["llm_calls"] == 7
    assert S["services"]["orders_api"]["error_rate"] == 0.003

def test_topology_and_dependencies():
    topo = get_topology()
    assert len(topo["services"]) == 4
    assert len(topo["dependencies"]) == 4

    S = create_initial_state()
    # Baseline pings should all succeed
    res = ping_dependency(S, "orders_api", "cache")
    assert res["reachable"] is True

    res_db = ping_dependency(S, "orders_api", "database")
    assert res_db["reachable"] is True
    assert res_db["integrity_ok"] is True

    # Invalid dependency
    res_inv = ping_dependency(S, "database", "orders_api")
    assert res_inv["status"] == "NO_DEPENDENCY"

def test_fault_1_cache_outage_and_restart():
    S = create_initial_state()
    inc = inject_fault(S, "cache_outage")
    assert inc["scenario"] == "cache_outage"
    assert S["services"]["cache"]["reachable"] is False
    assert S["services"]["worker"]["queue_depth"] == 380
    assert S["services"]["orders_api"]["error_rate"] == 0.48
    assert S["services"]["orders_api"]["latency_ms"] == 2400

    # Ping cache from orders_api should show connection refused
    ping = ping_dependency(S, "orders_api", "cache")
    assert ping["reachable"] is False

    # Verifier should fail
    eval_res = evaluate_single_check(S)
    assert eval_res["passed"] is False

    v_res = verify_recovery(S, sleep_fn=lambda _: None)
    assert v_res["status"] == "failed"

    # Apply fix
    fix_res = apply_restart_cache(S)
    assert fix_res["status"] == "success"
    assert S["services"]["cache"]["reachable"] is True
    assert S["services"]["worker"]["queue_depth"] < 20
    assert S["services"]["orders_api"]["error_rate"] < 0.02

    # Verifier should pass 3 consecutive cycles
    v_res2 = verify_recovery(S, sleep_fn=lambda _: None)
    assert v_res2["status"] == "passed"
    assert v_res2["consecutive_passes"] == 3

def test_fault_2_bad_config_and_rollback():
    S = create_initial_state()
    inject_fault(S, "bad_config")
    assert S["services"]["orders_api"]["error_rate"] == 1.0

    diff = diff_config(S, "orders_api")
    assert diff["has_diff"] is True
    assert "DATABASE_URL" in diff["changes"]

    # Rollback fix
    apply_rollback_config(S, "orders_api", "v2.4.0")
    assert S["services"]["orders_api"]["error_rate"] == 0.003
    diff_after = diff_config(S, "orders_api")
    assert diff_after["has_diff"] is False

    v_res = verify_recovery(S, sleep_fn=lambda _: None)
    assert v_res["status"] == "passed"

def test_fault_4_database_integrity():
    S = create_initial_state()
    inject_fault(S, "database_integrity")
    assert S["services"]["database"]["integrity_ok"] is False
    assert S["services"]["orders_api"]["error_rate"] == 0.22

    ping = ping_dependency(S, "orders_api", "database")
    assert ping["integrity_ok"] is False

    logs = query_logs(S, "database", 10)
    assert any("checksum mismatch" in l["message"] for l in logs["logs"])
