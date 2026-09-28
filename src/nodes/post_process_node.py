"""ReportValidate (post_process) — anti-suppression + S-3 citation gate + output safety.

Validates the draft compliance report rendered by main: asserts the assessment was generated
(non-suppressible), then applies the S-3 content gate (relocated from the old agent-class
`_security_gate_output`): MANDATORY KB-provenance citation (kb_version + as-of date),
secret-leakage redaction, and prompt-injection blanking. Produces `formatted_output` (returned by
the graph as `output`).
Node contract: execute(self, state) -> dict; status is an AgentStatus enum (SUCCESS / ERROR — the
framework has no COMPLETE/RUNNING).
"""

from __future__ import annotations

from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import RET_C2_108_State
from src.services.output_safety import apply_output_safety


# -- Where this answer came from ----------------------------------------------
#
# The corpus behind this answer is written into src/ and ships with the template. The module
# holding it says so ("Offline/CI: deterministic corpus above ... production replaces this
# with an injected client"), but the ANSWER did not, so it read exactly like an answer from a
# live system of record.
#
# That gap is what lets a fixture result carry the authority of real data. Labelling does not
# make an answer correct -- it stops it overstating where it came from, which is a different
# and smaller claim.

_SOURCE_LABEL_KEYS = (
    "kb_snapshot",
    "kb_as_of_date",
    "snapshot_date",
    "policy_snapshot_date",
    "baseline_snapshot_date",
    "kb_version",
)


def _snapshot_from(state: dict[str, Any]) -> str:
    for key in _SOURCE_LABEL_KEYS:
        value = state.get(key)
        if value:
            return str(value)
    return ""


def source_label(state: dict[str, Any]) -> str:
    """The provenance footer for the full answer."""
    snapshot = _snapshot_from(state)
    when = f"snapshot {snapshot}" if snapshot else "no snapshot date recorded"
    return (
        "\n\n---\n"
        f"**Source of this answer.** Grounded in a reference corpus bundled with this "
        f"template ({when}), not a live query against a system of record. Treat it as a "
        "starting point for a decision rather than the decision: verify against the "
        "authoritative source before acting on it.\n"
        "本回答は本テンプレートに同梱された参照コーパスに基づくものであり、記録システムへの"
        "照会結果ではありません。実行前に必ず正本をご確認ください。"
    )


def source_note(state: dict[str, Any]) -> str:
    """One line for `result`, which is what the Marketplace runner renders."""
    snapshot = _snapshot_from(state)
    when = f", snapshot {snapshot}" if snapshot else ""
    return (
        f" [Source: reference corpus bundled with this template{when}; not a system of "
        "record -- verify before acting.]"
    )


class PostProcessNode(FunctionNode):
    # S-1: internal pipeline node reached only after the pre_process gate; declared explicitly
    # (every FunctionNode subclass must declare required_trust_level) and kept at VERIFIED_EXTERNAL
    # so a VERIFIED_EXTERNAL caller passes all nodes (INTERNAL would wrongly block the caller).
    required_trust_level = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: RET_C2_108_State) -> dict[str, Any]:
        final_output = state.get("final_output", "")
        audit_generated = state.get("audit_generated", False)
        kb_version = state.get("kb_version", "")
        kb_as_of_date = state.get("kb_as_of_date", "")

        # Anti-suppression (non-negotiable): the assessment must have been generated.
        if not audit_generated:
            emit_trace_event(
                "post_process_complete",
                {
                    "reason": "anti-suppression",
                    "citations_present": False,
                    "redaction_triggered": False,
                    "output_chars": 0,
                },
                state,
            )
            return {
                "citations_present": False,
                "redaction_triggered": False,
                "formatted_output": {"report": "", "citations_present": False, "redaction_triggered": False},
                "status": AgentStatus.ERROR.value,
                "error_log": ["S-3 violation: audit_generated is False (anti-suppression)"],
            }

        # S-3 output safety: MANDATORY citation gate + secret redaction + injection check.
        safety = apply_output_safety(
            final_output,
            audit_generated=True,
            kb_version=kb_version,
            kb_as_of_date=kb_as_of_date,
        )
        final_output = safety["final_output"]
        citations_present = safety["citations_present"]
        redaction_triggered = safety["redaction_triggered"]

        if safety.get("error"):
            emit_trace_event(
                "post_process_complete",
                {
                    "reason": safety["error"],
                    "citations_present": citations_present,
                    "redaction_triggered": redaction_triggered,
                    "output_chars": len(final_output),
                },
                state,
            )
            return {
                "final_output": final_output,
                "citations_present": citations_present,
                "redaction_triggered": redaction_triggered,
                "formatted_output": {
                    "report": final_output,
                    "citations_present": citations_present,
                    "redaction_triggered": redaction_triggered,
                },
                "status": AgentStatus.ERROR.value,
                "error_log": [safety["error"]],
            }

        emit_trace_event(
            "post_process_complete",
            {
                "citations_present": citations_present,
                "redaction_triggered": redaction_triggered,
                "output_chars": len(final_output),
            },
            state,
        )
        # Say where this answer came from, on the document itself.
        final_output = final_output + source_label(state)
        return {
            "final_output": final_output,
            "citations_present": citations_present,
            "redaction_triggered": redaction_triggered,
            "formatted_output": {
                "report": final_output,
                "citations_present": citations_present,
                "redaction_triggered": redaction_triggered,
            },
            "status": AgentStatus.SUCCESS.value,
        }
