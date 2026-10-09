"""proofOps state management.
Centralized state dict S representing the operational environment and incident lifecycle.
"""
from typing import Any, Dict, List, Optional
import time
import copy

BASELINE_SERVICES: Dict[str, Dict[str, Any]] = {
    "orders_api": {
        "status": "healthy",
        "error_rate": 0.003,      # 0.3%
        "latency_ms": 120,        # 120 ms
        "memory_pct": 41,         # 41%
        "cpu_pct": 22,
        "version": "v2.4.0",
        "healthy": True,
    },
    "worker": {
        "status": "healthy",
        "queue_depth": 4,         # queue 4
        "error_rate": 0.0,
        "cpu_pct": 15,
        "healthy": True,
    },
    "cache": {
        "status": "healthy",
        "reachable": True,
        "hit_rate": 0.94,         # hit rate 94%
        "memory_pct": 35,
        "healthy": True,
    },
    "database": {
        "status": "healthy",
        "connections": 18,        # 18/100 connections
        "max_connections": 100,
        "integrity_ok": True,     # integrity ok
        "healthy": True,
    },
}

BASELINE_CONFIG: Dict[str, Dict[str, Any]] = {
    "current": {
        "DATABASE_URL": "postgresql://orders_usr:secret@pg-cluster:5432/orders_prod",
        "CACHE_URL": "redis://cache-cluster:6379/0",
        "WORKER_CONCURRENCY": "8",
        "LOG_LEVEL": "INFO",
        "TIMEOUT_SECONDS": "5",
    },
    "previous": {
        "DATABASE_URL": "postgresql://orders_usr:secret@pg-cluster:5432/orders_prod",
        "CACHE_URL": "redis://cache-cluster:6379/0",
        "WORKER_CONCURRENCY": "8",
        "LOG_LEVEL": "INFO",
        "TIMEOUT_SECONDS": "5",
    },
}

BASELINE_DEPLOYMENTS: List[Dict[str, Any]] = [
    {
        "id": "dep-891",
        "service": "orders_api",
        "version": "v2.4.0",
        "minutes_ago": 180,
        "status": "successful",
        "author": "ci-runner@prod",
        "commit": "a1b2c3d",
    }
]

def create_initial_state() -> Dict[str, Any]:
    """Returns a fresh state dictionary S conforming to specification."""
    return {
        "phase": "IDLE",  # IDLE|INVESTIGATING|AWAITING_APPROVAL|REMEDIATING|VERIFYING|RESOLVED|ESCALATED
        "services": copy.deepcopy(BASELINE_SERVICES),
        "config": copy.deepcopy(BASELINE_CONFIG),
        "deployments": copy.deepcopy(BASELINE_DEPLOYMENTS),
        "incident": None,
        "hypotheses": [],
        "timeline": [],
        "contents": [],
        "pending": None,
        "memory": [],
        "llm_calls": 0,
        "mode": "gemini",
        "mode_reason": "Gemini API initialized",
        "diag_calls": 0,
        "recovery_seconds": None,
        "tick_count": 0,
    }

def reset_environment(S: Dict[str, Any]) -> None:
    """Restores baseline and clears everything except memory and llm_calls."""
    saved_memory = copy.deepcopy(S.get("memory", []))
    saved_llm_calls = S.get("llm_calls", 0)
    saved_mode = S.get("mode", "gemini")
    saved_mode_reason = S.get("mode_reason", "")

    fresh = create_initial_state()
    S.clear()
    S.update(fresh)

    S["memory"] = saved_memory
    S["llm_calls"] = saved_llm_calls
    S["mode"] = saved_mode
    S["mode_reason"] = saved_mode_reason

def add_timeline_entry(
    S: Dict[str, Any],
    actor: str,
    kind: str,
    text: str,
    tier: Optional[str] = None
) -> None:
    """Appends an event to the incident timeline."""
    t_str = time.strftime("%H:%M:%S", time.gmtime())
    entry = {
        "t": t_str,
        "actor": actor,  # agent | human | system
        "kind": kind,    # alert | check | hypothesis | action | approval | verification | resolution | escalation
        "text": text,
        "tier": tier or "info",  # read | reversible | approval | blocked | info
    }
    S.setdefault("timeline", []).append(entry)
