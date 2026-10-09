"""Live SVG topology renderer for proofOps simulated orders platform."""
from typing import Any, Dict

def render_topology_svg(S: Dict[str, Any]) -> str:
    """Generates an animated, state-aware SVG microservice topology map."""
    services = S.get("services", {})
    orders_api = services.get("orders_api", {})
    worker = services.get("worker", {})
    cache = services.get("cache", {})
    database = services.get("database", {})

    def get_color(svc_data: Dict[str, Any]) -> str:
        status = svc_data.get("status", "healthy")
        if status == "healthy":
            return "#10b981"  # Emerald
        if status == "degraded":
            return "#f59e0b"  # Amber
        return "#ef4444"      # Red

    def get_fill(svc_data: Dict[str, Any]) -> str:
        status = svc_data.get("status", "healthy")
        if status == "healthy":
            return "#064e3b"
        if status == "degraded":
            return "#78350f"
        return "#7f1d1d"

    c_orders = get_color(orders_api)
    c_worker = get_color(worker)
    c_cache = get_color(cache)
    c_db = get_color(database)

    f_orders = get_fill(orders_api)
    f_worker = get_fill(worker)
    f_cache = get_fill(cache)
    f_db = get_fill(database)

    # Edge colors
    cache_down = not cache.get("reachable", True) or cache.get("status") == "down"
    edge_orders_cache = "#ef4444" if cache_down else "#38bdf8"
    edge_worker_cache = "#ef4444" if cache_down else "#38bdf8"

    db_bad = not database.get("integrity_ok", True) or database.get("status") != "healthy"
    edge_orders_db = "#ef4444" if db_bad else "#38bdf8"
    edge_orders_worker = "#38bdf8"

    svg = f"""
    <div style="background: #090e1a; border: 1px solid #1e293b; border-radius: 12px; padding: 12px; margin-bottom: 12px;">
    <svg viewBox="0 0 740 260" width="100%" height="240" xmlns="http://www.w3.org/2000/svg" style="font-family: system-ui, -apple-system, sans-serif;">
        <defs>
            <linearGradient id="grid-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#0e1726" />
                <stop offset="100%" stop-color="#080c14" />
            </linearGradient>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
            </marker>
            <marker id="arrow-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#ef4444" />
            </marker>
            <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
        </defs>

        <!-- Background grid styling -->
        <rect width="100%" height="100%" fill="url(#grid-grad)" rx="8" />

        <!-- Connecting Link Lines -->
        <!-- orders_api (120, 130) -> cache (390, 50) -->
        <path d="M 180 110 C 270 90, 310 60, 370 50" fill="none" stroke="{edge_orders_cache}" stroke-width="2.5" stroke-dasharray="{"4,4" if cache_down else "none"}" marker-end="{"url(#arrow-red)" if cache_down else "url(#arrow)"}" />
        <text x="270" y="70" fill="#94a3b8" font-size="10" font-weight="600">redis:6379</text>

        <!-- orders_api (120, 130) -> database (390, 210) -->
        <path d="M 180 150 C 270 170, 310 200, 370 210" fill="none" stroke="{edge_orders_db}" stroke-width="2.5" stroke-dasharray="{"4,4" if db_bad else "none"}" marker-end="{"url(#arrow-red)" if db_bad else "url(#arrow)"}" />
        <text x="260" y="200" fill="#94a3b8" font-size="10" font-weight="600">pg:5432</text>

        <!-- orders_api (120, 130) -> worker (600, 130) -->
        <path d="M 180 130 L 530 130" fill="none" stroke="{edge_orders_worker}" stroke-width="2" marker-end="url(#arrow)" stroke-opacity="0.6" />
        <text x="350" y="124" fill="#94a3b8" font-size="10" font-weight="600">grpc:async</text>

        <!-- worker (600, 130) -> cache (440, 50) -->
        <path d="M 570 110 C 530 75, 490 60, 460 55" fill="none" stroke="{edge_worker_cache}" stroke-width="2.5" stroke-dasharray="{"4,4" if cache_down else "none"}" marker-end="{"url(#arrow-red)" if cache_down else "url(#arrow)"}" />

        <!-- NODE 1: orders_api -->
        <g transform="translate(60, 80)">
            <rect width="130" height="95" rx="10" fill="{f_orders}" fill-opacity="0.25" stroke="{c_orders}" stroke-width="2" />
            <circle cx="20" cy="22" r="6" fill="{c_orders}" />
            <text x="32" y="26" fill="#f8fafc" font-size="12" font-weight="700">orders_api</text>
            <text x="14" y="44" fill="#cbd5e1" font-size="10">Status: {orders_api.get('status','ok').upper()}</text>
            <text x="14" y="60" fill="#cbd5e1" font-size="10">Err: {orders_api.get('error_rate', 0.0)*100:.1f}%</text>
            <text x="14" y="76" fill="#cbd5e1" font-size="10">Lat: {orders_api.get('latency_ms', 0)}ms</text>
        </g>

        <!-- NODE 2: cache -->
        <g transform="translate(370, 10)">
            <rect width="130" height="85" rx="10" fill="{f_cache}" fill-opacity="0.25" stroke="{c_cache}" stroke-width="2" />
            <circle cx="20" cy="22" r="6" fill="{c_cache}" />
            <text x="32" y="26" fill="#f8fafc" font-size="12" font-weight="700">cache (Redis)</text>
            <text x="14" y="44" fill="#cbd5e1" font-size="10">Status: {cache.get('status','ok').upper()}</text>
            <text x="14" y="60" fill="#cbd5e1" font-size="10">Reachable: {"YES" if cache.get('reachable') else "NO (REFUSED)"}</text>
            <text x="14" y="74" fill="#cbd5e1" font-size="10">Hit rate: {cache.get('hit_rate', 0.0)*100:.0f}%</text>
        </g>

        <!-- NODE 3: database -->
        <g transform="translate(370, 160)">
            <rect width="130" height="85" rx="10" fill="{f_db}" fill-opacity="0.25" stroke="{c_db}" stroke-width="2" />
            <circle cx="20" cy="22" r="6" fill="{c_db}" />
            <text x="32" y="26" fill="#f8fafc" font-size="12" font-weight="700">database (PG)</text>
            <text x="14" y="44" fill="#cbd5e1" font-size="10">Status: {database.get('status','ok').upper()}</text>
            <text x="14" y="60" fill="#cbd5e1" font-size="10">Pool: {database.get('connections',18)}/100</text>
            <text x="14" y="74" fill="{"#10b981" if database.get('integrity_ok') else '#ef4444'}" font-size="10" font-weight="700">Integrity: {"OK" if database.get('integrity_ok') else "FAILED_CHECKSUM"}</text>
        </g>

        <!-- NODE 4: worker -->
        <g transform="translate(540, 80)">
            <rect width="130" height="95" rx="10" fill="{f_worker}" fill-opacity="0.25" stroke="{c_worker}" stroke-width="2" />
            <circle cx="20" cy="22" r="6" fill="{c_worker}" />
            <text x="32" y="26" fill="#f8fafc" font-size="12" font-weight="700">worker (Async)</text>
            <text x="14" y="44" fill="#cbd5e1" font-size="10">Status: {worker.get('status','ok').upper()}</text>
            <text x="14" y="60" fill="{"#ef4444" if worker.get('queue_depth',0)>50 else '#cbd5e1'}" font-size="10" font-weight="{"700" if worker.get('queue_depth',0)>50 else '400'}">Queue: {worker.get('queue_depth', 0)} jobs</text>
            <text x="14" y="76" fill="#cbd5e1" font-size="10">CPU: {worker.get('cpu_pct', 15)}%</text>
        </g>
    </svg>
    </div>
    """
    return svg
