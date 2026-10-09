"""Incident memory and postmortem store for proofOps.
Stores resolved incidents across sessions and retrieves similar incidents by signature.
"""
from typing import Any, Dict, List, Optional
import json
import os
import time

SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "seed_incidents.json")

def load_seed_memory() -> List[Dict[str, Any]]:
    """Loads seed incidents from JSON if present."""
    if os.path.exists(SEED_FILE):
        try:
            with open(SEED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_postmortem(S: Dict[str, Any], summary: str) -> Dict[str, Any]:
    """Automatically executed when incident is successfully resolved and verified.
    Saves incident signature, root cause, resolution, and duration to S['memory'].
    """
    incident = S.get("incident") or {}
    record = {
        "id": incident.get("id", f"inc-{int(time.time())}"),
        "scenario": incident.get("scenario", "unknown"),
        "signature": incident.get("signature", ""),
        "name": incident.get("name", "Unknown Incident"),
        "alert": incident.get("alert", ""),
        "summary": summary,
        "resolved_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "recovery_seconds": S.get("recovery_seconds"),
        "hypotheses": S.get("hypotheses", []),
        "remediation_actions": [
            t["text"] for t in S.get("timeline", []) if t.get("kind") == "action"
        ],
    }

    # Store in S['memory']
    memory_list = S.setdefault("memory", [])
    memory_list.append(record)

    return record

def find_similar_incident(S: Dict[str, Any], signature: str) -> Dict[str, Any]:
    """Searches memory for incidents matching signature or related tokens."""
    memory_list = S.get("memory", [])
    if not memory_list:
        seed = load_seed_memory()
        if seed:
            memory_list = seed

    if not memory_list:
        return {
            "found": False,
            "count": 0,
            "message": "No previous incidents recorded in memory. This appears to be a zero-day or novel incident.",
            "matches": [],
        }

    # Token match or exact signature match
    matches = []
    sig_lower = (signature or "").lower()
    sig_tokens = set(sig_lower.replace("|", " ").replace(":", " ").replace("_", " ").split())

    for item in memory_list:
        item_sig = (item.get("signature") or "").lower()
        item_scenario = (item.get("scenario") or "").lower()
        item_alert = (item.get("alert") or "").lower()

        # Direct match
        if sig_lower and (sig_lower in item_sig or item_sig in sig_lower or item_scenario in sig_lower):
            matches.append(item)
            continue

        # Token overlap
        item_tokens = set(item_sig.replace("|", " ").replace(":", " ").replace("_", " ").split())
        overlap = sig_tokens.intersection(item_tokens)
        if len(overlap) >= 2:
            matches.append(item)

    if matches:
        return {
            "found": True,
            "count": len(matches),
            "message": f"Found {len(matches)} matching incident(s) in organizational memory.",
            "matches": [
                {
                    "incident_id": m.get("id"),
                    "scenario": m.get("scenario"),
                    "name": m.get("name"),
                    "signature": m.get("signature"),
                    "summary": m.get("summary"),
                    "effective_actions": m.get("remediation_actions", []),
                    "recovery_seconds": m.get("recovery_seconds"),
                }
                for m in matches
            ],
        }

    return {
        "found": False,
        "count": 0,
        "message": f"No memory match found for signature '{signature}'.",
        "matches": [],
    }
