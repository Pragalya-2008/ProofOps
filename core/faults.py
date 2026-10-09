"""Fault injection and remediation simulator for proofOps.
Defines the 4 challenge scenarios and deterministic fix state transitions.
"""
from typing import Any, Dict
import time
import copy
from core.state import add_timeline_entry

SCENARIOS = {
    "cache_outage": {
        "id": "inc-2026-101",
        "scenario": "cache_outage",
        "name": "Redis Cache Process Outage",
        "alert": "CRITICAL: orders_api error rate > 45%, latency spike > 2000ms",
        "severity": "CRITICAL",
        "signature": "orders_api:503_upstream_timeout|cache:connection_refused",
    },
    "bad_config": {
        "id": "inc-2026-102",
        "scenario": "bad_config",
        "name": "Faulty Deployment Configuration (Missing Env)",
        "alert": "FATAL: orders_api service down (100% errors, crashloop)",
        "severity": "FATAL",
        "signature": "orders_api:missing_DATABASE_URL|failed_to_start",
    },
    "repeat_cache_outage": {
        "id": "inc-2026-103",
        "scenario": "repeat_cache_outage",
        "name": "Recurrent Redis Cache Outage",
        "alert": "CRITICAL: orders_api error rate > 45%, latency spike > 2000ms",
        "severity": "CRITICAL",
        "signature": "orders_api:503_upstream_timeout|cache:connection_refused",
    },
    "database_integrity": {
        "id": "inc-2026-104",
        "scenario": "database_integrity",
        "name": "Database Table Checksum Mismatch",
        "alert": "CRITICAL: database data corruption / checksum mismatch detected",
        "severity": "CRITICAL",
        "signature": "database:checksum_mismatch|orders_api:22pct_error",
    },
}

def inject_fault(S: Dict[str, Any], scenario_name: str) -> Dict[str, Any]:
    """Injects a simulated fault into state S and initializes the incident."""
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_name}'")

    meta = SCENARIOS[scenario_name]
    now_ts = time.time()

    S["incident"] = {
        "id": meta["id"],
        "scenario": meta["scenario"],
        "name": meta["name"],
        "alert": meta["alert"],
        "severity": meta["severity"],
        "signature": meta["signature"],
        "started_at": now_ts,
    }
    S["phase"] = "INVESTIGATING"
    S["hypotheses"] = []
    S["contents"] = []
    S["pending"] = None
    S["diag_calls"] = 0
    S["recovery_seconds"] = None
    S["tick_count"] = 0

    services = S["services"]

    if scenario_name in ("cache_outage", "repeat_cache_outage"):
        # Cache down
        services["cache"]["status"] = "down"
        services["cache"]["reachable"] = False
        services["cache"]["hit_rate"] = 0.0
        services["cache"]["healthy"] = False

        # Worker degraded, queue 4 -> 380
        services["worker"]["status"] = "degraded"
        services["worker"]["queue_depth"] = 380
        services["worker"]["healthy"] = False

        # orders_api down, error 48%, latency 2400 ms, memory ~43%
        services["orders_api"]["status"] = "down"
        services["orders_api"]["error_rate"] = 0.48
        services["orders_api"]["latency_ms"] = 2400
        services["orders_api"]["memory_pct"] = 43
        services["orders_api"]["healthy"] = False

        # Database healthy
        services["database"]["status"] = "healthy"
        services["database"]["connections"] = 18
        services["database"]["integrity_ok"] = True
        services["database"]["healthy"] = True

    elif scenario_name == "bad_config":
        # Deployment v2.4.1 went out 12 min ago
        S["deployments"].insert(0, {
            "id": "dep-892",
            "service": "orders_api",
            "version": "v2.4.1",
            "minutes_ago": 12,
            "status": "deployed",
            "author": "alex.dev@prod",
            "commit": "f4e5d6c",
        })

        # Config diff shows DATABASE_URL removed
        prev_cfg = copy.deepcopy(S["config"]["current"])
        curr_cfg = copy.deepcopy(prev_cfg)
        curr_cfg.pop("DATABASE_URL", None)

        S["config"]["previous"] = prev_cfg
        S["config"]["current"] = curr_cfg

        # orders_api down, error 100%
        services["orders_api"]["status"] = "down"
        services["orders_api"]["error_rate"] = 1.0
        services["orders_api"]["latency_ms"] = 0
        services["orders_api"]["version"] = "v2.4.1"
        services["orders_api"]["healthy"] = False

        # Others healthy
        services["cache"]["status"] = "healthy"
        services["cache"]["reachable"] = True
        services["cache"]["healthy"] = True

        services["worker"]["status"] = "healthy"
        services["worker"]["queue_depth"] = 4
        services["worker"]["healthy"] = True

        services["database"]["status"] = "healthy"
        services["database"]["integrity_ok"] = True
        services["database"]["healthy"] = True

    elif scenario_name == "database_integrity":
        # Database degraded, integrity check failed
        services["database"]["status"] = "degraded"
        services["database"]["integrity_ok"] = False
        services["database"]["healthy"] = False

        # orders_api errors 22%
        services["orders_api"]["status"] = "degraded"
        services["orders_api"]["error_rate"] = 0.22
        services["orders_api"]["latency_ms"] = 350
        services["orders_api"]["healthy"] = False

        # Cache and worker healthy
        services["cache"]["status"] = "healthy"
        services["cache"]["reachable"] = True
        services["cache"]["healthy"] = True

        services["worker"]["status"] = "healthy"
        services["worker"]["queue_depth"] = 4
        services["worker"]["healthy"] = True

    add_timeline_entry(
        S,
        actor="system",
        kind="alert",
        text=f"Incident {meta['id']} fired: {meta['alert']} (Severity: {meta['severity']})",
        tier="info",
    )

    return S["incident"]

def apply_restart_cache(S: Dict[str, Any]) -> Dict[str, Any]:
    """Remediation: restart_cache makes cache healthy and initiates queue drain."""
    services = S.get("services", {})
    cache = services.get("cache", {})
    worker = services.get("worker", {})
    orders_api = services.get("orders_api", {})

    # Cache is now up
    cache["status"] = "healthy"
    cache["reachable"] = True
    cache["hit_rate"] = 0.94
    cache["healthy"] = True

    # Queue drains over 2-3 ticks; simulate progress
    worker["status"] = "healthy"
    worker["queue_depth"] = 12  # Drained below 20
    worker["healthy"] = True

    # orders_api stabilizes back to healthy parameters
    orders_api["status"] = "healthy"
    orders_api["error_rate"] = 0.003
    orders_api["latency_ms"] = 120
    orders_api["healthy"] = True

    return {
        "status": "success",
        "action": "restart_cache",
        "result": "Cache process restarted. Listening on :6379, socket ready. Queue drained to 12 jobs. orders_api error rate restored to 0.3%.",
    }

def apply_rollback_config(S: Dict[str, Any], service: str, to_version: str) -> Dict[str, Any]:
    """Remediation: rollback_config restores previous configuration."""
    cfg = S.get("config", {})
    prev = cfg.get("previous", {})
    cfg["current"] = copy.deepcopy(prev)

    services = S.get("services", {})
    orders_api = services.get("orders_api", {})
    orders_api["status"] = "healthy"
    orders_api["error_rate"] = 0.003
    orders_api["latency_ms"] = 120
    orders_api["version"] = to_version or "v2.4.0"
    orders_api["healthy"] = True

    # Update deployments list
    deployments = S.get("deployments", [])
    deployments.insert(0, {
        "id": "dep-893",
        "service": service,
        "version": to_version or "v2.4.0",
        "minutes_ago": 0,
        "status": "rolled_back",
        "author": "proofOps-safety-gate",
        "commit": "rollback-auto",
    })

    return {
        "status": "success",
        "action": "rollback_config",
        "service": service,
        "to_version": to_version,
        "result": f"Configuration for {service} rolled back to {to_version}. DATABASE_URL restored. Service passed readiness checks.",
    }
