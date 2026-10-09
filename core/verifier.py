"""Recovery verifier for proofOps.
Enforces multi-point verification across all critical service invariants:
- orders_api healthy
- error_rate < 2% (0.02)
- latency_ms < 300 ms
- queue_depth < 20
- cache reachable
- database integrity ok
Requires 3 checks in a row, 1 second apart (injectable sleep for testing).
"""
from typing import Any, Callable, Dict, List, Optional
import time

def evaluate_single_check(S: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates the 6 recovery invariants at a point in time."""
    services = S.get("services", {})
    orders_api = services.get("orders_api", {})
    worker = services.get("worker", {})
    cache = services.get("cache", {})
    database = services.get("database", {})

    c1_orders_ok = (orders_api.get("status") == "healthy")
    c2_error_ok = (orders_api.get("error_rate", 1.0) < 0.02)  # < 2%
    c3_latency_ok = (orders_api.get("latency_ms", 9999) < 300)  # < 300 ms
    c4_queue_ok = (worker.get("queue_depth", 999) < 20)        # < 20
    c5_cache_ok = (cache.get("reachable", False) is True)
    c6_db_ok = (database.get("integrity_ok", False) is True)

    passed = (c1_orders_ok and c2_error_ok and c3_latency_ok and c4_queue_ok and c5_cache_ok and c6_db_ok)

    return {
        "passed": passed,
        "checks": {
            "orders_api_status_healthy": {"passed": c1_orders_ok, "value": orders_api.get("status")},
            "orders_api_error_below_2pct": {"passed": c2_error_ok, "value": f"{orders_api.get('error_rate', 0.0)*100:.1f}%"},
            "orders_api_latency_below_300ms": {"passed": c3_latency_ok, "value": f"{orders_api.get('latency_ms', 0)}ms"},
            "worker_queue_below_20": {"passed": c4_queue_ok, "value": worker.get("queue_depth")},
            "cache_reachable": {"passed": c5_cache_ok, "value": cache.get("reachable")},
            "database_integrity_ok": {"passed": c6_db_ok, "value": database.get("integrity_ok")},
        }
    }

def verify_recovery(
    S: Dict[str, Any],
    sleep_fn: Optional[Callable[[float], None]] = None,
    delay_between_checks: float = 1.0
) -> Dict[str, Any]:
    """Runs 3 consecutive verification passes.
    Returns status: 'passed' only if all 3 pass.
    """
    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    checks_record: List[Dict[str, Any]] = []

    for check_idx in range(1, 4):
        eval_res = evaluate_single_check(S)
        checks_record.append({
            "iteration": check_idx,
            "timestamp": time.strftime("%H:%M:%S", time.gmtime()),
            "passed": eval_res["passed"],
            "details": eval_res["checks"],
        })

        if not eval_res["passed"]:
            # Short-circuit on failure
            return {
                "status": "failed",
                "consecutive_passes": check_idx - 1,
                "required_passes": 3,
                "message": f"Verification failed on check {check_idx}/3: invariants not satisfied.",
                "history": checks_record,
            }

        if check_idx < 3 and delay_between_checks > 0:
            sleeper(delay_between_checks)

    # All 3 consecutive passed
    # Calculate recovery duration if incident has started_at
    incident = S.get("incident")
    if incident and incident.get("started_at"):
        S["recovery_seconds"] = round(time.time() - incident["started_at"], 1)

    return {
        "status": "passed",
        "consecutive_passes": 3,
        "required_passes": 3,
        "message": "All 3 verification cycles passed. System operates within healthy baseline.",
        "history": checks_record,
    }
