"""Theme and styling definitions for proofOps."""
import streamlit as st

CUSTOM_CSS = """
<style>
/* Main container layout */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2.5rem;
    max-width: 1380px;
}

/* Header bar */
.proofops-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.8rem 1.2rem;
    background: linear-gradient(135deg, #0e1628 0%, #151f38 100%);
    border: 1px solid #1e293b;
    border-radius: 12px;
    margin-bottom: 1.2rem;
}

.proofops-brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.proofops-logo {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    color: white;
    font-weight: 800;
    font-size: 1.2rem;
    width: 38px;
    height: 38px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
}

.proofops-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0;
    letter-spacing: -0.02em;
}

.proofops-subtitle {
    font-size: 0.8rem;
    color: #94a3b8;
    margin: 0;
}

/* Phase Badges */
.phase-badge {
    display: inline-block;
    padding: 0.35rem 0.85rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.phase-IDLE {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
}

.phase-INVESTIGATING {
    background-color: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    border: 1px solid #3b82f6;
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.2);
}

.phase-AWAITING_APPROVAL {
    background-color: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid #f59e0b;
    animation: pulse-border 1.5s infinite;
}

.phase-REMEDIATING {
    background-color: rgba(139, 92, 246, 0.15);
    color: #c084fc;
    border: 1px solid #8b5cf6;
}

.phase-VERIFYING {
    background-color: rgba(14, 165, 233, 0.15);
    color: #38bdf8;
    border: 1px solid #0ea5e9;
}

.phase-RESOLVED {
    background-color: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid #10b981;
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.25);
}

.phase-ESCALATED {
    background-color: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid #ef4444;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.25);
}

/* Risk Tier Badges */
.tier-badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
}
.tier-read { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
.tier-reversible { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981; }
.tier-approval { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid #f59e0b; }
.tier-blocked { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }

/* Pulse animation */
@keyframes pulse-border {
    0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
    70% { box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
    100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}

/* Service Metric Card */
.service-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 1rem;
    margin-bottom: 0.75rem;
}
.service-card.healthy { border-left: 4px solid #10b981; }
.service-card.degraded { border-left: 4px solid #f59e0b; }
.service-card.down { border-left: 4px solid #ef4444; }

/* Hypothesis Card */
.hyp-card {
    background: #0d1526;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 0.9rem;
    margin-bottom: 0.75rem;
}
.hyp-confirmed { border-left: 4px solid #10b981; background: #0c1c2b; }
.hyp-eliminated { border-left: 4px solid #64748b; opacity: 0.65; }
.hyp-open { border-left: 4px solid #3b82f6; }

/* Safety Warning Box */
.safety-box {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 1rem;
    margin: 0.75rem 0;
}
</style>
"""

def apply_theme():
    """Injects custom CSS styles into Streamlit app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
