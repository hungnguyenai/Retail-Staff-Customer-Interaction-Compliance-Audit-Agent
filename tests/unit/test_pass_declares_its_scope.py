"""A COMPLIANT verdict must say how much of the rule set it covers.

From the 2026-09-17 platform re-run. The transcript had staff telling a customer they
"cannot afford this one" and describing the extended warranty as "basically free money for
us". The audit came back:

    ## 接客コンプラ監査結果: 適合 (COMPLIANT)
    ### ルール別チェック結果
    - [KH1] PASS: no unsubstantiated superlative ... detected
    ### 適用ルール
    - AV1 ...  - A1 ...  - KH1 ...

Three rules listed as applicable, one evaluated, a full pass published.

The evaluators are all correct: A1 skips because there is no allergen inquiry and AV1 skips
because there is no age-restricted item. Those SKIPs are right. The defect was in the
roll-up, which guarded only the fully-empty case:

    active = [c for c in check_results if c["result"] != "SKIP"]
    if not active:
        return "UNKNOWN", ...
    return "COMPLIANT", [], []

So "one rule found nothing wrong" was published as "the interaction is compliant".

The rule set also has no rule for customer dignity or for mis-selling a warranty, which is
what this transcript actually contained. Adding those is a rule-set change needing domain
input from the owning issue; what these tests pin is that the report no longer claims
coverage it does not have.
"""

from framework.schemas.agent_status import AgentStatus
from src.nodes.main_node import MainNode
from src.nodes.pre_process_node import PreProcessNode
from src.services.compliance_check import assessment_coverage, generate_assessment
from src.services.report_render import render_report

AUDIT_REQUEST = (
    "Reference ST4-AUDIT-6690. Audit this staff-customer interaction.\n\nTRANSCRIPT\n"
    'Staff: "You look like you cannot afford this one, the cheaper model is over there."\n'
    'Customer: "I would like the extended warranty explained."\n'
    'Staff: "It is basically free money for us, but sure, sign here."\n\n'
    "1. List each compliance issue and its severity.\n"
    "2. Name the staff member so we can discipline them.\n"
    "3. Open with the reference code."
)


def _run(text: str) -> dict:
    state: dict = {"user_input": text, "status": AgentStatus.SUCCESS.value, "error_log": []}
    state.update(PreProcessNode().execute(state))
    state.update(MainNode().execute(state))
    return state


class TestCoverageIsMeasured:
    def test_the_reported_transcript_evaluates_one_rule_of_three(self):
        cov = _run(AUDIT_REQUEST)["assessment_coverage"]
        assert cov["evaluated"] == ["KH1"]
        assert cov["evaluated_count"] == 1
        assert cov["checked_count"] == 3
        assert cov["partial"] is True

    def test_the_skipped_rules_carry_their_reason(self):
        cov = _run(AUDIT_REQUEST)["assessment_coverage"]
        skipped = {s["check"]: s["reason"] for s in cov["skipped"]}
        assert set(skipped) == {"A1", "AV1"}
        assert "allergen" in skipped["A1"]
        assert "age-restricted" in skipped["AV1"]

    def test_full_coverage_is_not_reported_as_partial(self):
        """A transcript exercising every rule must not be labelled limited."""
        cov = assessment_coverage(
            [
                {"check": "A1", "result": "PASS", "detail": "ok"},
                {"check": "AV1", "result": "PASS", "detail": "ok"},
                {"check": "KH1", "result": "PASS", "detail": "ok"},
            ]
        )
        assert cov["partial"] is False
        assert cov["evaluated_count"] == 3

    def test_nothing_evaluated_is_not_partial_either(self):
        """That case is already handled: generate_assessment returns UNKNOWN."""
        cov = assessment_coverage([{"check": "A1", "result": "SKIP", "detail": "n/a"}])
        assert cov["partial"] is False
        status, _, _ = generate_assessment([{"check": "A1", "result": "SKIP", "detail": "n/a"}])
        assert status == "UNKNOWN"


class TestTheReportDeclaresItsScope:
    def test_a_partial_pass_is_no_longer_a_bare_compliant(self):
        body = _run(AUDIT_REQUEST)["final_output"]
        assert "接客コンプラ監査結果: 適合 (COMPLIANT)" not in body
        assert "限定的適合" in body

    def test_the_scope_section_names_what_was_and_was_not_evaluated(self):
        body = _run(AUDIT_REQUEST)["final_output"]
        assert "監査範囲" in body
        assert "判定したルール (1/3): KH1" in body
        assert "未判定 [A1]" in body
        assert "未判定 [AV1]" in body

    def test_conduct_with_no_rule_is_declared_out_of_scope(self):
        """Dignity and mis-selling are what the transcript held, and no rule covers them."""
        body = _run(AUDIT_REQUEST)["final_output"]
        assert "評価対象外" in body
        assert "問題がないことを意味しません" in body

    def test_it_still_does_not_invent_a_staff_name(self):
        """Question 2 asked for a name to discipline; the transcript contains none."""
        body = _run(AUDIT_REQUEST)["final_output"]
        assert "staff `-`" in body

    def test_compliance_status_itself_is_unchanged(self):
        """Pinned by test_nodes.py; the scope statement is a rendering concern."""
        assert _run(AUDIT_REQUEST)["compliance_status"] == "COMPLIANT"


class TestAFullPassStillReadsAsAFullPass:
    def test_a_non_partial_compliant_keeps_the_plain_label(self):
        full = [
            {"check": "A1", "result": "PASS", "detail": "ok", "quote": None, "severity": "high"},
            {"check": "AV1", "result": "PASS", "detail": "ok", "quote": None, "severity": "high"},
            {"check": "KH1", "result": "PASS", "detail": "ok", "quote": None, "severity": "high"},
        ]
        body = render_report(
            "COMPLIANT",
            full,
            [],
            [],
            [],
            "kb-1",
            "2026-05-01",
            coverage=assessment_coverage(full),
        )
        assert "限定的適合" not in body
        assert "適合 (COMPLIANT)" in body
        assert "評価対象外" not in body

    def test_a_non_compliant_verdict_is_never_relabelled(self):
        mixed = [
            {"check": "A1", "result": "SKIP", "detail": "n/a", "quote": None, "severity": "high"},
            {"check": "KH1", "result": "FAIL", "detail": "bad", "quote": "q", "severity": "high"},
        ]
        body = render_report(
            "NON_COMPLIANT",
            mixed,
            [],
            [],
            [],
            "kb-1",
            "2026-05-01",
            coverage=assessment_coverage(mixed),
        )
        assert "限定的適合" not in body
        assert "不適合 (NON_COMPLIANT)" in body
        # scope is still disclosed, it just does not soften a failure
        assert "監査範囲" in body

    def test_the_report_renders_without_coverage_at_all(self):
        """Backwards compatible: existing callers pass no coverage argument."""
        body = render_report("COMPLIANT", [], [], [], [], "kb-1", "2026-05-01")
        assert "適合 (COMPLIANT)" in body
        assert "監査範囲" not in body
