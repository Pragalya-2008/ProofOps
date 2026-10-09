"""Simulated environment sandbox for proofOps orders platform.
Models 4 services: orders_api, worker, cache, database.
"""
from typing import Any, Dict, List, Optional
import math
import time

SERVICE_DEPENDENCIES = {
    "orders_api": ["cache", "database", "worker"],
    "worker": ["cache"],
    "cache": [],
    "database": [],
}

def _cosmetic_noise(seed_key: str, tick: int) -> float:
    """Deterministic +/-1% cosmetic noise generator for healthy metrics."""
    # Deterministic sinusoidal variance between -0.01 and +0.01
    val = math.sin((hash(seed_key) % 1000) + tick * 0.7)
    return round(val * 0.01, 4)

def get_topology() -> Dict[str, Any]:
    """Returns services topology and dependency edges."""
    return {
        "services": [
            {"name": "orders_api", "type": "http_api", "role": "Order ingestion and dispatch gateway"},
            {"name": "worker", "type": "background_worker", "role": "Asynchronous order processor"},
            {"name": "cache", "type": "in_memory_cache", "role": "Session store & rate limiter (Redis)"},
            {"name": "database", "type": "relational_db", "role": "Primary transactional store (PostgreSQL)"},
        ],
        "dependencies": [
            {"from": "orders_api", "to": "cache", "protocol": "redis://6379", "critical": True},
            {"from": "orders_api", "to": "database", "protocol": "postgres://5432", "critical": True},
            {"from": "orders_api", "to": "worker", "protocol": "grpc://50051", "critical": False},
            {"from": "worker", "to": "cache", "protocol": "redis://6379", "critical": True},
        ],
    }

def ping_dependency(S: Dict[str, Any], from_service: str, to_service: str) -> Dict[str, Any]:
    """Tests network and protocol connectivity between two services."""
    allowed = SERVICE_DEPENDENCIES.get(from_service, [])
    if to_service not in allowed:
        return {
            "from": from_service,
            "to": to_service,
            "status": "NO_DEPENDENCY",
            "message": f"Service '{from_service}' does not declare an active dependency on '{to_service}'."
        }

    services = S.get("services", {})
    target = services.get(to_service, {})

    if to_service == "cache":
        reachable = target.get("reachable", True)
        if not reachable or target.get("status") == "down":
            return {
                "from": from_service,
                "to": to_service,
                "reachable": False,
                "status": "CONNECTION_REFUSED",
                "latency_ms": None,
                "error": "dial tcp cache:6379: connect: connection refused (cache process unreachable)",
            }
        return {
            "from": from_service,
            "to": to_service,
            "reachable": True,
            "status": "HEALTHY",
            "latency_ms": 1.8,
            "message": "PONG (roundtrip 1.8ms)",
        }

    if to_service == "database":
        integrity_ok = target.get("integrity_ok", True)
        if not integrity_ok:
            return {
                "from": from_service,
                "to": to_service,
                "reachable": True,
                "status": "DEGRADED",
                "integrity_ok": False,
                "latency_ms": 420.0,
                "error": "Query failed: checksum validation failed on table 'orders'; relation inconsistent",
            }
        return {
            "from": from_service,
            "to": to_service,
            "reachable": True,
            "status": "HEALTHY",
            "latency_ms": 4.5,
            "integrity_ok": True,
        }

    if to_service == "worker":
        q = target.get("queue_depth", 0)
        return {
            "from": from_service,
            "to": to_service,
            "reachable": True,
            "status": "HEALTHY" if q < 50 else "BACKLOGGED",
            "queue_depth": q,
            "latency_ms": 8.0,
        }

    return {"from": from_service, "to": to_service, "status": "UNKNOWN"}

def check_health(S: Dict[str, Any], service: str) -> Dict[str, Any]:
    """Returns service health status and granular health check results."""
    services = S.get("services", {})
    if service not in services:
        return {"service": service, "status": "UNKNOWN", "error": f"Unknown service '{service}'"}

    svc = services[service]
    status = svc.get("status", "healthy")
    healthy = (status == "healthy")

    details: Dict[str, Any] = {"service": service, "status": status, "healthy": healthy}

    if service == "orders_api":
        details["checks"] = {
            "http_liveness": healthy or status == "degraded",
            "http_readiness": healthy,
            "error_rate": f"{svc.get('error_rate', 0.0) * 100:.1f}%",
            "latency_ms": svc.get("latency_ms", 120),
            "memory_pct": svc.get("memory_pct", 41),
        }
    elif service == "worker":
        details["checks"] = {
            "worker_threads_active": True,
            "queue_depth": svc.get("queue_depth", 4),
            "drain_rate_per_sec": 45 if healthy else 0,
        }
    elif service == "cache":
        details["checks"] = {
            "tcp_socket_listening": svc.get("reachable", True),
            "hit_rate": f"{svc.get('hit_rate', 0.0) * 100:.1f}%",
            "memory_pct": svc.get("memory_pct", 35),
        }
    elif service == "database":
        details["checks"] = {
            "tcp_socket_listening": True,
            "connections": f"{svc.get('connections', 18)}/{svc.get('max_connections', 100)}",
            "integrity_validation": "PASSED" if svc.get("integrity_ok", True) else "FAILED_CHECKSUM_ERROR",
        }

    return details

def get_metrics(S: Dict[str, Any], service: str) -> Dict[str, Any]:
    """Returns numerical operational metrics for a service with realistic noise."""
    services = S.get("services", {})
    if service not in services:
        return {"error": f"Unknown service '{service}'"}

    svc = services[service]
    tick = S.get("tick_count", 0)

    res: Dict[str, Any] = {"service": service, "status": svc.get("status", "healthy")}

    if service == "orders_api":
        is_healthy = svc.get("status") == "healthy"
        noise = _cosmetic_noise("orders_api", tick) if is_healthy else 0.0
        base_err = svc.get("error_rate", 0.003)
        base_lat = svc.get("latency_ms", 120)
        base_mem = svc.get("memory_pct", 41)
        base_cpu = svc.get("cpu_pct", 22)

        res["error_rate_pct"] = round(max(0.0, (base_err * 100) * (1.0 + noise)), 2)
        res["latency_ms"] = round(base_lat * (1.0 + noise), 1)
        res["memory_pct"] = round(base_mem * (1.0 + noise), 1)
        res["cpu_pct"] = round(base_cpu * (1.0 + noise), 1)
        res["version"] = svc.get("version", "v2.4.0")

    elif service == "worker":
        is_healthy = svc.get("status") == "healthy"
        noise = _cosmetic_noise("worker", tick) if is_healthy else 0.0
        res["queue_depth"] = svc.get("queue_depth", 4)
        res["error_rate_pct"] = round(svc.get("error_rate", 0.0) * 100, 2)
        res["cpu_pct"] = round(svc.get("cpu_pct", 15) * (1.0 + noise), 1)

    elif service == "cache":
        reachable = svc.get("reachable", True)
        noise = _cosmetic_noise("cache", tick) if reachable else 0.0
        res["reachable"] = reachable
        res["hit_rate_pct"] = round(svc.get("hit_rate", 0.94) * 100 * (1.0 + noise), 1) if reachable else 0.0
        res["memory_pct"] = round(svc.get("memory_pct", 35) * (1.0 + noise), 1) if reachable else 0.0

    elif service == "database":
        integrity_ok = svc.get("integrity_ok", True)
        noise = _cosmetic_noise("database", tick) if integrity_ok else 0.0
        res["connections"] = svc.get("connections", 18)
        res["max_connections"] = svc.get("max_connections", 100)
        res["integrity_ok"] = integrity_ok

    return res

def query_logs(S: Dict[str, Any], service: str, minutes: int = 15) -> Dict[str, Any]:
    """Returns recent log lines for the given service."""
    incident = S.get("incident")
    scenario = incident.get("scenario") if incident else None
    services = S.get("services", {})
    svc_data = services.get(service, {})
    status = svc_data.get("status", "healthy")

    lines: List[Dict[str, str]] = []
    now_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    if status == "healthy":
        lines = [
            {"level": "INFO", "timestamp": now_ts, "message": f"[{service}] Healthcheck passed 200 OK"},
            {"level": "INFO", "timestamp": now_ts, "message": f"[{service}] Processing normal traffic without errors"},
            {"level": "DEBUG", "timestamp": now_ts, "message": f"[{service}] Connections in pool steady"},
        ]
        return {"service": service, "window_minutes": minutes, "log_count": len(lines), "logs": lines}

    # Incident-specific logs
    if scenario in ("cache_outage", "repeat_cache_outage"):
        if service == "cache":
            lines = [
                {"level": "CRITICAL", "timestamp": now_ts, "message": "Fatal error: Segmentation fault in jemalloc arena 0"},
                {"level": "ERROR", "timestamp": now_ts, "message": "Process terminated with exit code 139 (SIGSEGV)"},
                {"level": "ERROR", "timestamp": now_ts, "message": "cache unreachable: connection refused on port 6379"},
            ]
        elif service == "worker":
            lines = [
                {"level": "ERROR", "timestamp": now_ts, "message": "Redis connection lost: connect: connection refused"},
                {"level": "WARN", "timestamp": now_ts, "message": "worker queue growing: 380 unacknowledged jobs"},
                {"level": "WARN", "timestamp": now_ts, "message": "Backing off retry every 5s..."},
            ]
        elif service == "orders_api":
            lines = [
                {"level": "WARN", "timestamp": now_ts, "message": "Cache lookup failed for session cache-cluster:6379"},
                {"level": "ERROR", "timestamp": now_ts, "message": "orders_api 503 upstream timeout after 2400ms"},
                {"level": "ERROR", "timestamp": now_ts, "message": "Degraded fallback cache exhausted; client requests failing"},
            ]
        elif service == "database":
            lines = [
                {"level": "INFO", "timestamp": now_ts, "message": "PostgreSQL connection pool healthy; 18 active connections"},
            ]

    elif scenario == "bad_config":
        if service == "orders_api":
            lines = [
                {"level": "INFO", "timestamp": now_ts, "message": "Starting orders_api container version v2.4.1..."},
                {"level": "ERROR", "timestamp": now_ts, "message": "missing required env DATABASE_URL in environment variables"},
                {"level": "FATAL", "timestamp": now_ts, "message": "orders_api failed to start: panic: runtime error: invalid memory address or nil pointer dereference (DB init)"},
                {"level": "ERROR", "timestamp": now_ts, "message": "Kubernetes CrashLoopBackOff: Container failed to pass liveness probe"},
            ]
        else:
            lines = [
                {"level": "INFO", "timestamp": now_ts, "message": f"[{service}] Operating normally"},
            ]

    elif scenario == "database_integrity":
        if service == "database":
            lines = [
                {"level": "CRITICAL", "timestamp": now_ts, "message": "CRITICAL checksum mismatch on orders table page 0x829f0"},
                {"level": "CRITICAL", "timestamp": now_ts, "message": "CRITICAL transaction integrity validation failed: relation inconsistent"},
                {"level": "ERROR", "timestamp": now_ts, "message": "Storage block bit-flip detected on NVMe volume vol-019e"},
            ]
        elif service == "orders_api":
            lines = [
                {"level": "ERROR", "timestamp": now_ts, "message": "SQL query failed: relation 'orders' contains invalid page header"},
                {"level": "ERROR", "timestamp": now_ts, "message": "Transaction aborted: 22% of write transactions throwing SQLSTATE 58P01"},
            ]
        else:
            lines = [
                {"level": "INFO", "timestamp": now_ts, "message": f"[{service}] Service running smoothly"},
            ]

    return {"service": service, "window_minutes": minutes, "log_count": len(lines), "logs": lines}

def diff_config(S: Dict[str, Any], service: str = "orders_api") -> Dict[str, Any]:
    """Returns the diff between current and previous configuration."""
    cfg = S.get("config", {})
    curr = cfg.get("current", {})
    prev = cfg.get("previous", {})

    diffs: Dict[str, Dict[str, Any]] = {}
    all_keys = set(curr.keys()).union(set(prev.keys()))
    for k in all_keys:
        curr_val = curr.get(k)
        prev_val = prev.get(k)
        if curr_val != prev_val:
            diffs[k] = {"current": curr_val, "previous": prev_val}

    return {
        "service": service,
        "has_diff": len(diffs) > 0,
        "changes": diffs,
        "current_config": curr,
        "previous_config": prev,
    }

def get_recent_deployments(S: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns the list of recent deployments."""
    return S.get("deployments", [])
