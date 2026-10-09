"""proofOps autonomous SRE agent loop.
Executes evidence-first incident investigation using Gemini Flash-Lite with
automatic function calling disabled, safety gating, turn caps, and fallback engine.
"""
from typing import Any, Callable, Dict, List, Optional
import time
import os

from google import genai
from google.genai import types

from core.state import add_timeline_entry
from core.tools import TOOL_DECLARATIONS, execute_tool
from core.fallback import run_fallback_step
from core.guardrails import get_tool_tier

MODEL_NAME = "gemini-2.5-flash-lite"

MAX_TURNS = 12
CALL_LIMIT = 30
MAX_DIAG_CALLS = 5

NON_DIAGNOSTIC_TOOLS = {
    "update_hypotheses",
    "verify_recovery",
    "page_human",
    "resolve_incident",
    "restart_cache",
    "rollback_config",
    "repair_database",
}

SYSTEM_INSTRUCTION = """You are proofOps, an autonomous evidence-first site reliability engineering agent responding to incidents on a simulated production orders platform.

OPERATIONAL PRINCIPLES:
1. INVESTIGATE READ-ONLY FIRST: Gather concrete telemetry (get_alert, get_topology, query_logs, get_metrics, check_health, ping_dependency, diff_config, find_similar_incident) before making any state changes.
2. COMPETING HYPOTHESES BOARD: Keep 2-3 competing root-cause hypotheses active on the visible board via update_hypotheses. Assign confidence (0.0 to 1.0), status ('open', 'eliminated', or 'confirmed'), and concrete evidence.
3. ORGANIZATIONAL MEMORY: Query find_similar_incident to leverage historical postmortems for fast diagnosis of recurring issues.
4. CODE SAFETY GATE:
   - Read tools: Safe observation.
   - Reversible fixes (restart_cache): Permitted for safe mitigation.
   - Approval tools (rollback_config): Changes requiring authorization will pause for human approval.
   - Blocked tools (repair_database): Dangerous in production; strictly blocked.
5. MANDATORY VERIFICATION: You CANNOT resolve an incident without first executing verify_recovery and confirming all 3 cycles pass.
6. ESCALATION: When an issue cannot be auto-fixed safely (e.g., database integrity corruption), page the human operator with page_human and include a detailed Evidence Packet.
7. DIAGNOSTIC BUDGET: You have a maximum of 5 diagnostic checks. Once reached, you must immediately decide: execute a permissible remediation or page_human.
"""

def _build_genai_client(api_key: str) -> Optional[genai.Client]:
    """Creates a google-genai Client if an API key is available."""
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def _get_api_key(secrets_dict: Optional[Dict[str, Any]] = None) -> str:
    """Reads GEMINI_API_KEY from secrets or environment."""
    if secrets_dict and secrets_dict.get("GEMINI_API_KEY"):
        return str(secrets_dict.get("GEMINI_API_KEY")).strip()
    return os.environ.get("GEMINI_API_KEY", "").strip()

def run_agent_turn(
    S: Dict[str, Any],
    api_key: Optional[str] = None,
    secrets_dict: Optional[Dict[str, Any]] = None,
    sleep_fn: Optional[Callable[[float], None]] = None
) -> Dict[str, Any]:
    """Executes a single autonomous turn of the proofOps agent loop."""
    phase = S.get("phase", "IDLE")
    if phase in ("RESOLVED", "ESCALATED", "AWAITING_APPROVAL"):
        return {"status": "paused_or_terminal", "phase": phase}

    incident = S.get("incident")
    if not incident:
        return {"status": "idle", "message": "No active incident"}

    # Resolve API Key
    key = api_key or _get_api_key(secrets_dict)

    # Check session LLM call limit
    if S.get("llm_calls", 0) >= CALL_LIMIT:
        S["mode"] = "fallback"
        S["mode_reason"] = f"Session Gemini call limit ({CALL_LIMIT}) reached. Switched to fallback."

    # If no key or in fallback mode, route to deterministic fallback engine
    if not key or S.get("mode") == "fallback":
        if not key and S.get("mode") != "fallback":
            S["mode"] = "fallback"
            S["mode_reason"] = "No GEMINI_API_KEY configured. Running in high-fidelity deterministic fallback mode."
        return run_fallback_step(S, sleep_fn=sleep_fn)

    # Initialize Gemini client
    client = _build_genai_client(key)
    if client is None:
        S["mode"] = "fallback"
        S["mode_reason"] = "Failed to initialize Gemini client. Switched to fallback."
        return run_fallback_step(S, sleep_fn=sleep_fn)

    # Initialize contents if empty
    contents = S.setdefault("contents", [])
    if not contents:
        initial_prompt = (
            f"ALERT TRIGGERED: {incident.get('alert')} (Severity: {incident.get('severity')}, Incident ID: {incident.get('id')}).\n"
            f"Please investigate the root cause read-only first, keep 2-3 competing hypotheses on the board, check memory for previous incidents, "
            f"apply code-safe remediation or page_human if blocked, and verify recovery."
        )
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=initial_prompt)]))

    # Prepare Gemini configuration
    gen_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.2,
        tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Generate content with retry once on error/429
    response = None
    retry_count = 0
    last_error = ""

    while retry_count < 2:
        try:
            S["llm_calls"] = S.get("llm_calls", 0) + 1
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=gen_config,
            )
            break
        except Exception as e:
            last_error = str(e)
            retry_count += 1
            if retry_count < 2:
                time.sleep(1.0)
            else:
                # Second failure -> switch to fallback
                S["mode"] = "fallback"
                S["mode_reason"] = f"Gemini API error ({last_error}). Switched to fallback mode."
                return run_fallback_step(S, sleep_fn=sleep_fn)

    if not response or not response.candidates:
        S["mode"] = "fallback"
        S["mode_reason"] = "Gemini returned empty candidate response."
        return run_fallback_step(S, sleep_fn=sleep_fn)

    model_content = response.candidates[0].content
    # Append the full model response to S['contents'] unchanged
    contents.append(model_content)

    # Extract function calls from parts
    parts = model_content.parts or []
    function_calls = [p.function_call for p in parts if getattr(p, "function_call", None) is not None]

    if not function_calls:
        # Model returned pure text without function call
        text_content = "".join([getattr(p, "text", "") or "" for p in parts])
        return {"status": "text_response", "text": text_content}

    # "Run only the FIRST function_call; answer extras with {"status":"skipped","message":"one tool at a time"}. Always return a function_response for every function_call."
    response_parts: List[types.Part] = []

    first_call = function_calls[0]
    first_name = first_call.name
    first_args = dict(first_call.args) if first_call.args else {}

    # Track diagnostic call count
    if first_name not in NON_DIAGNOSTIC_TOOLS:
        S["diag_calls"] = S.get("diag_calls", 0) + 1

    # Execute first tool
    tool_result = execute_tool(
        S,
        name=first_name,
        args=first_args,
        approved=False,
        sleep_fn=sleep_fn
    )

    # If diagnostic budget is reached, inject notice
    if S.get("diag_calls", 0) >= MAX_DIAG_CALLS and first_name not in NON_DIAGNOSTIC_TOOLS:
        if isinstance(tool_result, dict):
            tool_result["diagnostic_budget_alert"] = (
                f"Diagnostic budget reached ({S['diag_calls']}/{MAX_DIAG_CALLS} calls). "
                f"You must now decide: apply an authorized fix (restart_cache, rollback_config) or page_human."
            )

    response_parts.append(
        types.Part.from_function_response(name=first_name, response=tool_result)
    )

    # Answer extra function calls with skipped
    for extra_call in function_calls[1:]:
        skipped_res = {"status": "skipped", "message": "one tool at a time"}
        response_parts.append(
            types.Part.from_function_response(name=extra_call.name, response=skipped_res)
        )

    # Append function responses to contents
    contents.append(types.Content(role="user", parts=response_parts))

    return {
        "status": "tool_executed",
        "tool": first_name,
        "args": first_args,
        "result": tool_result,
        "diag_calls": S.get("diag_calls", 0),
        "phase": S.get("phase"),
    }

def run_investigation_until_pause(
    S: Dict[str, Any],
    api_key: Optional[str] = None,
    secrets_dict: Optional[Dict[str, Any]] = None,
    max_turns: int = MAX_TURNS,
    sleep_fn: Optional[Callable[[float], None]] = None
) -> Dict[str, Any]:
    """Runs autonomous agent turns until a pause point or terminal state is reached."""
    turn = 0
    history: List[Dict[str, Any]] = []

    while turn < max_turns:
        phase = S.get("phase", "IDLE")
        if phase in ("AWAITING_APPROVAL", "RESOLVED", "ESCALATED"):
            break

        turn += 1
        res = run_agent_turn(
            S,
            api_key=api_key,
            secrets_dict=secrets_dict,
            sleep_fn=sleep_fn
        )
        history.append(res)

    return {
        "turns_executed": turn,
        "final_phase": S.get("phase"),
        "history": history,
    }
