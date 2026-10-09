"""UI Components for proofOps incident response platform."""
from typing import Any, Dict, List
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time

def render_header(S: Dict[str, Any]):
    """Renders the top navigation and status bar."""
    phase = S.get("phase", "IDLE")
    mode = S.get("mode", "gemini")
    mode_reason = S.get("mode_reason", "")
    llm_calls = S.get("llm_calls", 0)
    diag_calls = S.get("diag_calls", 0)

    mode_label = "Gemini Flash-Lite" if mode == "gemini" else "Deterministic Fallback"
    mode_color = "#38bdf8" if mode == "gemini" else "#f59e0b"

    st.markdown(
        f"""
        <div class="proofops-header">
            <div class="proofops-brand">
                <div class="proofops-logo">⚡</div>
                <div>
                    <h1 class="proofops-title">proofOps</h1>
                    <p class="proofops-subtitle">Evidence-First Autonomous SRE & Auto-Healing Platform</p>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="text-align: right;">
                    <div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Engine Mode</div>
                    <div style="font-size: 0.85rem; font-weight: 700; color: {mode_color};">{mode_label}</div>
                </div>
                <div style="text-align: right; border-left: 1px solid #334155; padding-left: 1rem;">
                    <div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Diagnostics / LLM</div>
                    <div style="font-size: 0.85rem; font-weight: 700; color: #f8fafc;">{diag_calls}/5 Diag &bull; {llm_calls} Calls</div>
                </div>
                <div style="padding-left: 0.5rem;">
                    <span class="phase-badge phase-{phase}">{phase}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_incident_banner(S: Dict[str, Any]):
    """Renders current active incident banner or nominal status."""
    incident = S.get("incident")
    if not incident:
        st.markdown(
            """
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid #10b981; border-radius: 10px; padding: 0.9rem 1.2rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span style="font-size: 1.3rem;">🟢</span>
                    <div>
                        <strong style="color: #34d399; font-size: 0.95rem;">All Systems Nominal</strong>
                        <div style="color: #94a3b8; font-size: 0.8rem;">orders_api, cache, database, and background worker are operating within healthy SLOs.</div>
                    </div>
                </div>
                <div style="color: #64748b; font-size: 0.78rem;">Platform Baseline: Normal</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    sev = incident.get("severity", "HIGH")
    sev_color = "#ef4444" if sev in ("CRITICAL", "FATAL") else "#f59e0b"
    rec_sec = S.get("recovery_seconds")

    rec_badge = f"""<span style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 700; font-size: 0.78rem;">MTTR: {rec_sec}s</span>""" if rec_sec else ""

    st.markdown(
        f"""
        <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid {sev_color}; border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem;">
                        <span style="background: {sev_color}; color: #000; font-weight: 800; font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 4px;">{sev}</span>
                        <strong style="color: #f8fafc; font-size: 1.05rem;">{incident.get('name')}</strong>
                        <code style="color: #94a3b8; font-size: 0.78rem;">{incident.get('id')}</code>
                        {rec_badge}
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.85rem; font-family: monospace;">{incident.get('alert')}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase;">Signature</div>
                    <code style="font-size: 0.72rem; color: #38bdf8;">{incident.get('signature')}</code>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_hypotheses_board(S: Dict[str, Any]):
    """Renders the Competing Root-Cause Hypotheses Board."""
    st.subheader("🎯 Competing Root-Cause Hypotheses Board")
    hypotheses = S.get("hypotheses", [])

    if not hypotheses:
        st.info("Agent has not yet published hypotheses. Investigation is initializing or running baseline observation.")
        return

    cols = st.columns(len(hypotheses))
    for idx, hyp in enumerate(hypotheses):
        status = hyp.get("status", "open").lower()
        conf = float(hyp.get("confidence", 0.0))
        cause = hyp.get("cause", "Unknown Cause")
        ev = hyp.get("evidence", "No evidence recorded.")

        status_class = f"hyp-{status}"
        status_badge_color = {
            "confirmed": "#10b981",
            "eliminated": "#64748b",
            "open": "#3b82f6",
        }.get(status, "#94a3b8")

        with cols[idx]:
            st.markdown(
                f"""
                <div class="hyp-card {status_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: {status_badge_color};">
                            ● {status.upper()}
                        </span>
                        <span style="font-size: 0.85rem; font-weight: 700; color: #f8fafc;">
                            {int(conf * 100)}%
                        </span>
                    </div>
                    <h4 style="margin: 0 0 0.5rem 0; font-size: 0.95rem; color: #f8fafc;">{cause}</h4>
                    <div style="width: 100%; background: #1e293b; height: 6px; border-radius: 3px; margin-bottom: 0.75rem; overflow: hidden;">
                        <div style="width: {int(conf * 100)}%; background: {status_badge_color}; height: 100%;"></div>
                    </div>
                    <div style="font-size: 0.78rem; color: #94a3b8; line-height: 1.4;">
                        <strong style="color: #cbd5e1;">Evidence:</strong> {ev}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

def render_safety_gate_approval(S: Dict[str, Any]):
    """Renders human-in-the-loop approval panel when an action requires authorization."""
    pending = S.get("pending")
    if not pending or S.get("phase") != "AWAITING_APPROVAL":
        return

    st.markdown(
        f"""
        <div class="safety-box">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.2rem;">⚠️</span>
                <strong style="color: #fbbf24; font-size: 1rem;">Human Approval Required by Code Safety Gate</strong>
                <span class="tier-badge tier-approval">APPROVAL TIER</span>
            </div>
            <p style="margin: 0 0 0.5rem 0; color: #cbd5e1; font-size: 0.85rem;">
                The autonomous agent proposed high-impact remediation:
                <code style="color: #fbbf24; font-weight: 700;">{pending.get('tool')}({pending.get('args')})</code>
            </p>
            <p style="margin: 0; color: #94a3b8; font-size: 0.8rem;">
                <strong>Reason:</strong> {pending.get('reason')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_verification_gauge(S: Dict[str, Any]):
    """Renders the 3-point invariant recovery verification status."""
    last_v = S.get("last_verification")
    if not last_v:
        return

    passed = (last_v.get("status") == "passed")
    passes = last_v.get("consecutive_passes", 0)
    req = last_v.get("required_passes", 3)

    badge_color = "#10b981" if passed else "#ef4444"
    st.markdown(
        f"""
        <div style="background: #0d1526; border: 1px solid {badge_color}; border-radius: 10px; padding: 0.9rem 1.2rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span style="font-size: 1.3rem;">{"✅" if passed else "⏳"}</span>
                    <div>
                        <strong style="color: #f8fafc; font-size: 0.95rem;">Multi-Point Verification: {last_v.get('status','').upper()}</strong>
                        <div style="color: #94a3b8; font-size: 0.8rem;">{last_v.get('message')}</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 1.1rem; font-weight: 800; color: {badge_color};">{passes}/{req} Passes</span>
                    <div style="font-size: 0.72rem; color: #94a3b8;">1s interval required</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_telemetry_metrics(S: Dict[str, Any]):
    """Renders live microservice metric gauges and KPIs."""
    services = S.get("services", {})
    orders_api = services.get("orders_api", {})
    worker = services.get("worker", {})
    cache = services.get("cache", {})
    database = services.get("database", {})

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="service-card {orders_api.get('status','healthy')}">
                <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;">orders_api</div>
                <div style="font-size: 1.4rem; font-weight: 700; color: #f8fafc;">
                    {orders_api.get('error_rate', 0.0)*100:.1f}% <span style="font-size: 0.75rem; color: #94a3b8;">errors</span>
                </div>
                <div style="font-size: 0.8rem; color: #cbd5e1;">Latency: {orders_api.get('latency_ms', 120)} ms</div>
                <div style="font-size: 0.75rem; color: #64748b;">Mem: {orders_api.get('memory_pct', 41)}% &bull; {orders_api.get('version', 'v2.4.0')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        q = worker.get("queue_depth", 4)
        st.markdown(
            f"""
            <div class="service-card {worker.get('status','healthy')}">
                <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;">worker queue</div>
                <div style="font-size: 1.4rem; font-weight: 700; color: {'#ef4444' if q>20 else '#f8fafc'};">
                    {q} <span style="font-size: 0.75rem; color: #94a3b8;">jobs</span>
                </div>
                <div style="font-size: 0.8rem; color: #cbd5e1;">CPU: {worker.get('cpu_pct', 15)}%</div>
                <div style="font-size: 0.75rem; color: #64748b;">Status: {worker.get('status','healthy').upper()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        reachable = cache.get("reachable", True)
        st.markdown(
            f"""
            <div class="service-card {cache.get('status','healthy')}">
                <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;">cache (redis)</div>
                <div style="font-size: 1.4rem; font-weight: 700; color: {'#10b981' if reachable else '#ef4444'};">
                    {'ONLINE' if reachable else 'REFUSED'}
                </div>
                <div style="font-size: 0.8rem; color: #cbd5e1;">Hit Rate: {cache.get('hit_rate', 0.94)*100:.0f}%</div>
                <div style="font-size: 0.75rem; color: #64748b;">Port: 6379</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        integrity_ok = database.get("integrity_ok", True)
        st.markdown(
            f"""
            <div class="service-card {database.get('status','healthy')}">
                <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase;">database (postgres)</div>
                <div style="font-size: 1.4rem; font-weight: 700; color: {'#10b981' if integrity_ok else '#ef4444'};">
                    {'CHECKSUM OK' if integrity_ok else 'CORRUPT'}
                </div>
                <div style="font-size: 0.8rem; color: #cbd5e1;">Pool: {database.get('connections', 18)}/{database.get('max_connections', 100)}</div>
                <div style="font-size: 0.75rem; color: #64748b;">Status: {database.get('status','healthy').upper()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_timeline(S: Dict[str, Any]):
    """Renders the incident timeline audit log."""
    st.subheader("📜 Incident Timeline & Safety Audit Stream")
    timeline = S.get("timeline", [])

    if not timeline:
        st.caption("No events logged in the timeline yet.")
        return

    # Render in reverse-chronological order or chronological
    for item in reversed(timeline):
        actor = item.get("actor", "agent")
        kind = item.get("kind", "check")
        text = item.get("text", "")
        tier = item.get("tier", "info")
        t = item.get("t", "")

        actor_badge = {
            "agent": "🤖 Agent",
            "human": "👤 Human",
            "system": "⚙️ System",
        }.get(actor, actor)

        tier_html = f"""<span class="tier-badge tier-{tier}">{tier}</span>""" if tier != "info" else ""

        st.markdown(
            f"""
            <div style="padding: 0.45rem 0.75rem; border-left: 2px solid #334155; margin-left: 0.5rem; margin-bottom: 0.4rem; background: #0b1120; border-radius: 0 6px 6px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.75rem; color: #94a3b8; font-family: monospace;">{t}</span>
                        <span style="font-size: 0.75rem; font-weight: 700; color: #e2e8f0;">{actor_badge}</span>
                        {tier_html}
                    </div>
                    <span style="font-size: 0.7rem; color: #64748b; text-transform: uppercase;">{kind}</span>
                </div>
                <div style="font-size: 0.82rem; color: #cbd5e1; font-family: -apple-system, sans-serif;">{text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_escalation_packet_view(S: Dict[str, Any]):
    """Renders the comprehensive Evidence Packet when incident is escalated."""
    if S.get("phase") != "ESCALATED":
        return

    packet = S.get("escalation_packet", {})
    st.error("🚨 HUMAN OPERATOR PAGED — AUTONOMOUS MITIGATION BLOCKED BY SAFETY GATE")

    with st.expander("📂 Evidence Packet for On-Call Engineer (Expand)", expanded=True):
        st.markdown(f"**Incident ID:** `{packet.get('incident_id')}` | **Scenario:** `{packet.get('scenario')}`")
        st.markdown(f"**Agent Summary:** {packet.get('agent_summary')}")
        st.markdown(f"**Recommended Next Step:** `{packet.get('recommended_next_step')}`")
        st.markdown(f"**Provided Evidence:** {packet.get('provided_evidence')}")
        st.json(packet.get("affected_services", {}))

def render_memory_section(S: Dict[str, Any]):
    """Renders the organizational memory and historical postmortems."""
    memory = S.get("memory", [])
    st.subheader(f"🧠 Organizational Memory ({len(memory)} Postmortems)")

    if not memory:
        st.caption("No historical postmortems in memory yet. Resolved incidents will automatically persist here.")
        return

    for idx, item in enumerate(reversed(memory)):
        with st.expander(f"📋 {item.get('name', 'Incident')} ({item.get('id', 'N/A')}) — {item.get('resolved_at', '')}"):
            st.markdown(f"**Signature:** `{item.get('signature')}`")
            st.markdown(f"**Summary:** {item.get('summary')}")
            if item.get("recovery_seconds"):
                st.markdown(f"**MTTR:** `{item.get('recovery_seconds')}s`")
            if item.get("remediation_actions"):
                st.markdown(f"**Effective Actions:** {', '.join(item.get('remediation_actions'))}")
