"""Main node — RuleRetrieve + ComplianceCheck + AssessmentGenerate + render (combined Main slot).

AgentBaseGraph runs a fixed pipeline (initialize → pre_process → main → post_process → finalize),
so the KB retrieval + allergen/景品表示法/age compliance checks + assessment + render steps are
orchestrated here. Per the design ((internal issue reference removed) §4) this template commits to a COMBINED Main slot
with an explicit error contract:
  - a missing audit context (pre_process failed) → ERROR with the anti-suppression invariant still
    recorded (audit_generated = True on the empty path so post_process's assertion is meaningful);
  - the compliance checks always run on whatever context was extracted.
The assessment generation is NON-SUPPRESSIBLE: audit_generated is always set True before returning
(post_process asserts it).

Node contract: execute(self, state) -> dict; status is an AgentStatus enum; no __call__/_invoke_impl.
An optional versioned KB service and LLM are injected via config; None → deterministic offline KB
stub / rule-based assessment so CI is fully testable.
"""

from __future__ import annotations

from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import RET_C2_108_State, from_json, to_json
from src.services.compliance_check import generate_assessment, run_checks, assessment_coverage
from src.services.compliance_kb import KB_AS_OF_DATE, KB_VERSION, ComplianceKBStub
from src.services.report_render import render_report


class MainNode(FunctionNode):
    # S-1: internal pipeline node reached only after the pre_process gate; declared explicitly
    # (every FunctionNode subclass must declare required_trust_level) and kept at VERIFIED_EXTERNAL
    # so a VERIFIED_EXTERNAL caller passes all nodes (INTERNAL would wrongly block the caller).
    required_trust_level = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, kb: Any = None, llm: Any = None) -> None:
        # Immutable injected deps only (no mutable per-invocation state on self).
        self._kb = kb
        self._llm = llm

    def execute(self, state: RET_C2_108_State) -> dict[str, Any]:
        context = from_json(state.get("audit_context"), None)
        # Propagate a pre_process failure: AgentBaseGraph always routes pre_process → main.
        if not context:
            # Anti-suppression invariant is recorded even on the empty path.
            return {
                "audit_generated": True,
                "compliance_status": "UNKNOWN",
                "status": AgentStatus.ERROR.value,
                "error_log": ["main: no audit context (input validation failed)"],
            }

        output_language = state.get("output_language", "ja")

        # RuleRetrieve — versioned KB (injected client or offline stub).
        kb = self._kb if self._kb is not None else ComplianceKBStub()
        kb_version = getattr(kb, "version", KB_VERSION)
        kb_as_of_date = getattr(kb, "as_of_date", KB_AS_OF_DATE)
        applied_rules = kb.applicable_rules(context)

        # AllergenDisclosure → KeihinVerbalClaim → AgeVerification (deterministic markers).
        check_results = run_checks(context)

        # AssessmentGenerate — rule-based decision (auditable, reproducible).
        compliance_status, flagged_quotes, remediation = generate_assessment(check_results)
        # How much of the declared rule set actually spoke. A pass resting on one rule
        # out of three used to be published as a full 適合.
        coverage = assessment_coverage(check_results, applied_rules)

        # Render — the draft cited report (post_process validates + S-3 asserts citations).
        final_output = render_report(
            compliance_status,
            check_results,
            flagged_quotes,
            remediation,
            applied_rules,
            kb_version,
            kb_as_of_date,
            staff_id=context.get("staff_id", ""),
            interaction_context=context.get("interaction_context", ""),
            output_language=output_language,
            coverage=coverage,
        )

        emit_trace_event(
            "assessment_complete",
            {
                "compliance_status": compliance_status,
                "checks_run": coverage["evaluated_count"],
                "checks_skipped": len(coverage["skipped"]),
                "partial_coverage": coverage["partial"],
                "flagged_quotes": len(flagged_quotes),
                "kb_version": kb_version,
                "audit_generated": True,
            },
            state,
        )
        return {
            "kb_version": kb_version,
            "kb_as_of_date": kb_as_of_date,
            "applied_rules": to_json(applied_rules),
            "check_results": to_json(check_results),
            "flagged_quotes": to_json(flagged_quotes),
            "compliance_status": compliance_status,
            "remediation_action": to_json(remediation),
            "assessment_coverage": coverage,
            "audit_generated": True,  # anti-suppression invariant
            "final_output": final_output,
            "status": AgentStatus.SUCCESS.value,
        }
