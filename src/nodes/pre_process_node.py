"""TranscriptNormalize + ContextExtract (pre_process) — validate the audit query + S-2 gate.

AgentCore node contract: override execute(self, state) -> dict; return a partial update; set
status (AgentStatus enum); never override __call__; no _invoke_impl. Runtime-provided transcripts
are external-trust (S-1): require VERIFIED_EXTERNAL. The S-2 input gate (injection block, length
bounds, interaction-context constraint, rule-set validation) lives in
src/services/context_parse.py before a compliance context is built.
"""

from __future__ import annotations

from typing import Any

import json

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import RET_C2_108_State, to_json
from src.services.context_parse import build_audit_context

_DEFAULT_OUTPUT_LANGUAGE = "ja"


def _coerce(state: dict[str, Any], key: str, default: Any) -> Any:
    """Read a field from state, falling back to a JSON object supplied on user_input."""
    if state.get(key) not in (None, ""):
        return state.get(key)
    raw = state.get("user_input", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and key in parsed:
                return parsed[key]
        except (ValueError, TypeError):
            pass
    return default


def _coerce_transcript(state: dict[str, Any]) -> str:
    if state.get("transcript"):
        return str(state["transcript"])
    raw = state.get("user_input", "")
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "transcript" in parsed:
            return str(parsed["transcript"])
    except (ValueError, TypeError):
        pass
    # Plain text → treat the whole input as the transcript.
    return str(raw)


class PreProcessNode(FunctionNode):
    """Validate + normalize the runtime audit query: S-2 gate, then build the context."""

    # S-1: runtime-provided transcripts are external-trust.
    required_trust_level = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: RET_C2_108_State) -> dict[str, Any]:
        transcript = _coerce_transcript(state)
        staff_id = _coerce(state, "staff_id", "")
        interaction_context = _coerce(state, "interaction_context", "unknown")
        store_region = _coerce(state, "store_region", "")
        rule_set = _coerce(state, "rule_set", None)
        output_language = _coerce(state, "output_language", _DEFAULT_OUTPUT_LANGUAGE)

        context, input_errors = build_audit_context(
            transcript,
            staff_id=staff_id,
            interaction_context=interaction_context,
            store_region=store_region,
            rule_set=rule_set,
        )

        if context is None:
            return {
                "output_language": str(output_language or _DEFAULT_OUTPUT_LANGUAGE),
                "audit_context": None,
                "input_errors": to_json(input_errors),
                "status": AgentStatus.ERROR.value,
                "error_log": ["S-2: audit query rejected by the input gate"],
            }

        emit_trace_event(
            "pre_process_complete",
            {
                "interaction_context": context["interaction_context"],
                "rules": len(context["rule_set"]),
                "input_errors": len(input_errors),
                "transcript_chars": len(context["transcript"]),
            },
            state,
        )
        return {
            "transcript": context["transcript"],
            "staff_id": context["staff_id"],
            "interaction_context": context["interaction_context"],
            "store_region": context["store_region"],
            "rule_set": to_json(context["rule_set"]),
            "output_language": str(output_language or _DEFAULT_OUTPUT_LANGUAGE),
            "audit_context": to_json(context),
            "input_errors": to_json(input_errors),
            "status": AgentStatus.SUCCESS.value,
        }
