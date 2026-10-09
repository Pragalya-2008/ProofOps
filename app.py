"""proofOps - Evidence-First Autonomous Incident-Response Platform.
Entry point for Streamlit application.
"""
import streamlit as st
import time

from core.state import create_initial_state, reset_environment
from core.faults import inject_fault, SCENARIOS
from core.agent import run_agent_turn, run_investigation_until_pause, MODEL_NAME
from core.tools import execute_tool
from ui.theme import apply_theme
from ui.topology_svg import render_topology_svg
from ui.components import (
    render_header,
    render_incident_banner,
    render_hypotheses_board,
    render_safety_gate_approval,
    render_verification_gauge,
    render_telemetry_metrics,
    render_timeline,
    render_escalation_packet_view,
    render_memory_section,
)

# Page configuration
st.set_page_config(
    page_title="proofOps - Autonomous Auto-Healing Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply sleek Datadog-inspired dark observability CSS
apply_theme()

# Initialize session state S
if "S" not in st.session_state:
    st.session_state["S"] = create_initial_state()

S = st.session_state["S"]

# Increment tick counter for cosmetic noise
S["tick_count"] = S.get("tick_count", 0) + 1

# ----------------- SIDEBAR CONTROLS -----------------
with st.sidebar:
    st.markdown("### ⚡ proofOps Control Plane")
    st.caption("CTRL+AI Challenge • PS-12 Auto-Heal")

    # API Key Configuration
    st.markdown("#### 🔑 Model & API Configuration")
    st.markdown(f"**Target Model:** `{MODEL_NAME}`")

    # Read from st.secrets if available
    secret_key = ""
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret_key = ""

    api_key_input = st.text_input(
        "Gemini API Key (optional):",
        value=secret_key,
        type="password",
        help="Leave blank to run in deterministic high-fidelity fallback mode.",
    )

    if api_key_input.strip():
        S["mode"] = "gemini"
        S["mode_reason"] = "Gemini Flash-Lite API Active"
    else:
        S["mode"] = "fallback"
        S["mode_reason"] = "Running in deterministic fallback mode (No API Key)"

    st.divider()

    # Scenario Injection
    st.markdown("#### 🚨 Inject Demo Scenario")
    scenario_choice = st.selectbox(
        "Select Scenario:",
        options=[
            ("cache_outage", "1. Cache Outage (Auto-Healed)"),
            ("repeat_cache_outage", "2. Repeat Cache Outage (Memory Accelerated)"),
            ("bad_config", "3. Bad Config (Rollback Needs Human Approval)"),
            ("database_integrity", "4. DB Integrity Fault (Repair Blocked, Paged)"),
        ],
        format_func=lambda x: x[1],
    )

    selected_scenario_id = scenario_choice[0]

    if st.button("🔥 Inject Fault & Trigger Alert", use_container_width=True, type="primary"):
        inject_fault(S, selected_scenario_id)
        st.rerun()

    st.divider()

    # Autonomous Investigation Controls
    st.markdown("#### 🤖 Agent Investigation")
    col_step, col_auto = st.columns(2)

    with col_step:
        step_clicked = st.button("Step Agent", use_container_width=True, disabled=(S["phase"] in ("IDLE", "RESOLVED", "ESCALATED", "AWAITING_APPROVAL")))

    with col_auto:
        auto_clicked = st.button("▶ Auto-Run", use_container_width=True, disabled=(S["phase"] in ("IDLE", "RESOLVED", "ESCALATED", "AWAITING_APPROVAL")))

    if step_clicked:
        run_agent_turn(S, api_key=api_key_input.strip(), sleep_fn=lambda _: None)
        st.rerun()

    if auto_clicked:
        run_investigation_until_pause(S, api_key=api_key_input.strip(), sleep_fn=lambda _: None)
        st.rerun()

    # Pending Approval Handlers
    if S.get("phase") == "AWAITING_APPROVAL" and S.get("pending"):
        st.warning("⚠️ Action pending your authorization!")
        c_app, c_deny = st.columns(2)
        with c_app:
            if st.button("✅ Approve", use_container_width=True, type="primary"):
                p = S["pending"]
                execute_tool(S, p["tool"], p["args"], approved=True, sleep_fn=lambda _: None)
                st.rerun()
        with c_deny:
            if st.button("❌ Deny Action", use_container_width=True):
                S["pending"] = None
                S["phase"] = "INVESTIGATING"
                st.rerun()

    st.divider()

    # Reset Environment
    if st.button("🔄 Reset Environment", use_container_width=True):
        reset_environment(S)
        st.rerun()

    st.caption("Reset restores baseline services, clears hypotheses and timeline, but preserves organizational memory and session call metrics.")


# ----------------- MAIN DASHBOARD -----------------
render_header(S)
render_incident_banner(S)

# Topology diagram and microservice metrics
st.markdown("### 🌐 Live Service Topology & Telemetry")
st.markdown(render_topology_svg(S), unsafe_allow_html=True)
render_telemetry_metrics(S)

# Safety Gate Approval Alert
render_safety_gate_approval(S)

# Verification status
render_verification_gauge(S)

# Escalation packet view if paged
render_escalation_packet_view(S)

# Competing Hypotheses Board
render_hypotheses_board(S)

st.divider()

# Timeline & Memory Split
col_left, col_right = st.columns([3, 2])

with col_left:
    render_timeline(S)

with col_right:
    render_memory_section(S)
