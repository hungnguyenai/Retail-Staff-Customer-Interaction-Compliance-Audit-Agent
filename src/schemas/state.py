"""State schema for RET-C2-108 — RetailInteractionComplianceAuditAgent.

# ADR-005: State must be a flat TypedDict (see ADR-005 for the prohibited alternatives).
# LangGraph checkpoints use msgpack serialization; Non-flat objects and nested
# containers (list[dict] / dict) are not msgpack-safe and cause silent
# corruption. Extend AgentState with primitive fields only. Compliance artifacts
# that are naturally list/dict are stored JSON-serialized as Optional[str] and
# (de)serialized at the node boundary via to_json / from_json. Do NOT add
# credentials, secrets, or other non-flat objects. (Field names are also kept clear of
# credential-like substrings per the state-safety proof-of-boundary scan.)

Shared fields (user_input, status, node_history, error_log, correlation_id,
caller_trust_level, formatted_output, etc.) are inherited from AgentState.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from framework.schemas.agent_state import AgentState


def to_json(value: Any) -> Optional[str]:
    """Serialize a list/dict State value to a compact JSON string (ADR-005, msgpack-safe).

    Returns None for None so the field stays a true Optional[str].
    """
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def from_json(value: Any, default: Any) -> Any:
    """Deserialize a JSON-string State value back to its list/dict form.

    Tolerant by design: None/empty -> default; an already-native list/dict (e.g. a value
    supplied directly in a unit test) passes through unchanged; a malformed string -> default.
    """
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class RET_C2_108_State(AgentState):
    # --- Input query (provided on user_input / state or defaults) ---
    transcript: str  # staff-customer interaction transcript (STT text)
    staff_id: str  # staff identifier (opaque; not a credential)
    interaction_context: str  # checkout | floor | phone | unknown
    store_region: str  # store / region identifier
    rule_set: Optional[str]  # JSON list[str] of dims to apply: allergen / keihin / age
    output_language: str  # ja | en | bilingual

    # --- TranscriptNormalize + ContextExtract (pre_process) output ---
    audit_context: Optional[str]  # JSON dict — normalized audit context
    input_errors: Optional[str]  # JSON list[{"field","reason"}] rejected by S-2

    # --- RuleRetrieve + ComplianceCheck + AssessmentGenerate (main) output ---
    kb_version: str  # versioned compliance-rule KB revision cited in the report
    kb_as_of_date: str  # KB as-of date (regulation snapshot)
    applied_rules: Optional[str]  # JSON list[{"rule_id","title"}] rules applied
    check_results: Optional[str]  # JSON list[{"check","result","detail","quote","severity"}]
    flagged_quotes: Optional[str]  # JSON list[{"rule","quote","severity"}] non-compliant quotes
    compliance_status: str  # COMPLIANT | NON_COMPLIANT | CONDITIONAL | UNKNOWN
    remediation_action: Optional[str]  # JSON list[str] manager remediation actions
    audit_generated: bool  # anti-suppression invariant: default False, set True by main

    # --- ReportValidate + S-3 (post_process) output ---
    final_output: str
    citations_present: bool  # non-suppressible S-3: kb_version + as-of date cited
    redaction_triggered: bool  # True if the S-3 secret-leakage redaction triggered
