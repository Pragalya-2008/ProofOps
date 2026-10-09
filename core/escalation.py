"""Escalation management and Evidence Packet generator for proofOps.
Compiles comprehensive incident telemetry and hypothesis state when human on-call is paged.
"""
from typing import Any, Dict, List
import time
from core.state import add_timeline_entry

def generate_evidence_packet(
    S: Dict[str, Any],
    summary: str,
    evidence: Any,
    recommended_next_step: str
) -> Dict[str, Any]:
    """Builds a rich, auditable Evidence Packet for the human operator."""
    incident = S.get("incident") or {}
    services = S.get("services") or {}
    hypotheses = S.get("hypotheses") or []
    timeline = S.get("timeline") or []

    packet = {
        "incident_id": incident.get("id", "N/A"),
        "scenario": incident.get("scenario", "manual_or_unknown"),
        "alert": incident.get("alert", "N/A"),
        "severity": incident.get("severity", "HIGH"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "agent_summary": summary,
        "recommended_next_step": recommended_next_step,
        "provided_evidence": evidence,
        "hypotheses_board": hypotheses,
        "affected_services": {
            name: {
                "status": data.get("status"),
                "healthy": data.get("healthy"),
            }
            for name, data in services.items()
        },
        "timeline_events_count": len(timeline),
    }

    return packet

def dispatch_escalation(
    S: Dict[str, Any],
    summary: str,
    evidence: Any,
    recommended_next_step: str
) -> Dict[str, Any]:
    """Paging action: transitions incident to ESCALATED and logs evidence packet."""
    packet = generate_evidence_packet(S, summary, evidence, recommended_next_step)
    S["phase"] = "ESCALATED"
    S["escalation_packet"] = packet

    add_timeline_entry(
        S,
        actor="agent",
        kind="escalation",
        text=f"PAGED HUMAN ON-CALL: {summary}. Recommended next step: {recommended_next_step}",
        tier="read",
    )

    return {
        "status": "escalated",
        "message": "Human on-call paged successfully with complete Evidence Packet.",
        "packet": packet,
    }
