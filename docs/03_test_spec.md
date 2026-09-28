# RET-C2-108 — Test Specification (`docs/03_test_spec.md`)

**Template ID:** RET-C2-108 · **Name:** RetailInteractionComplianceAuditAgent · **Cat 2 / RET**

Deterministic core (offline compliance-rule KB stub, no live LLM). Status convention: the framework
`AgentStatus` enum is `PENDING / SUCCESS / RETRY / ERROR / TIMEOUT / AWAITING_HUMAN / CANCELLED`
— there is **no `COMPLETE`/`RUNNING`**, so nodes return `SUCCESS` to advance and `ERROR` to halt.

## Unit tests (≥6 TC)

| TC | Node / Service | Input | Expected | Test |
|----|----------------|-------|----------|------|
| TC-01 | PreProcessNode (S-1) | `caller_trust_level=ANONYMOUS` | status ERROR (trust gate) | `test_security.test_trust_gate_blocks_anonymous` |
| TC-02 | PreProcessNode (S-1) | `VERIFIED_EXTERNAL` | status SUCCESS | `test_security.test_trust_gate_allows_verified_external` |
| TC-03 | context_parse (S-2) | injection transcript | context None; injection error | `test_services.test_build_context_rejects_injection` |
| TC-04 | context_parse (S-2) | `rule_set="allergen,bogus"` | unknown token dropped + flagged | `test_services.test_build_context_filters_unknown_rule` |
| TC-05 | context_parse (S-2) | empty transcript | context None + error | `test_services.test_build_context_empty_text_returns_none` |
| TC-06 | compliance_kb | `rule_set=["allergen"]` | A1 rule selected | `test_services.test_applicable_rules_include_a1_when_allergen_dim` |
| TC-07 | compliance_kb | default rule_set | A1 + KH1 + AV1 selected | `test_services.test_applicable_rules_include_all_three` |
| TC-08 | compliance_check | allergen reassurance | A1 FAIL | `test_services.test_allergen_fail_on_reassurance` |
| TC-09 | compliance_check | 業界最安値 claim | KH1 FAIL | `test_services.test_keihin_fail_on_superlative_claim` |
| TC-10 | compliance_check | age item, no verification | AV1 FAIL | `test_services.test_age_fail_when_no_verification` |
| TC-11 | compliance_check | no violation | assessment COMPLIANT | `test_services.test_assessment_compliant_when_no_violation` |
| TC-12 | compliance_check | a FAIL check | assessment NON_COMPLIANT | `test_services.test_assessment_non_compliant_on_fail` |
| TC-13 | report_render | ja report | KB citation present | `test_services.test_render_report_carries_citation` |
| TC-14 | report_render | bilingual | JA + EN report + flagged quotes | `test_services.test_render_report_bilingual` |
| TC-15 | PreProcessNode | valid transcript | SUCCESS; context built | `test_nodes.test_pre_process_success_builds_context` |
| TC-16 | MainNode | compliant transcript | status COMPLIANT; cited | `test_nodes.test_main_compliant_when_no_violation` |
| TC-17 | MainNode | no context | ERROR; `audit_generated=True` | `test_nodes.test_main_errors_without_context_but_sets_audit_flag` |
| TC-18 | PostProcessNode (S-3) | `audit_generated=False` | status ERROR | `test_nodes.test_post_process_anti_suppression_blocks_when_audit_missing` |
| TC-19 | State schema | minimal fields | field access works | `test_nodes.test_state_schema` |

## Proof-of-Boundary tests (≥3 PB)

| PB | Boundary | What is verified | Test file |
|----|----------|------------------|-----------|
| PB-01 | S-2 input gate | injection transcript blocked; empty transcript rejected | `test_pb_s2_input_gate.py` |
| PB-02 | S-2 context/rule-set bounds | unknown interaction_context coerced, unknown rule dropped | `test_pb_s2_input_gate.py` |
| PB-03 | S-3 anti-suppression | `audit_generated=False` → ERROR | `test_pb_s3_output_gate.py` |
| PB-04 | S-3 citation gate | missing KB citation blocked; present passes | `test_pb_s3_output_gate.py` |
| PB-05 | S-3 secret redaction | API-key pattern redacted in report | `test_pb_s3_output_gate.py` |
| PB-06 | Import isolation | no `from agenticstar` / `import agenticstar` in src/ | `test_import_isolation.py` |
| PB-07 | State safety | State is flat TypedDict; no Pydantic/credentials | `test_state_safety.py` |
| PB-08 | Invoke / gate order | pre_process (S-2) → main → post_process (S-3); S-1 refuses ANONYMOUS | `test_pb_invoke_order.py` |

## Coverage

Every `src/` module is exercised: nodes (`test_nodes`), S-1 (`test_security`), services
(`test_services`), full graph (`integration/test_graph`), boundaries (`proof_of_boundary/*`).
No stubbed-only test functions (gate-stub-check). Dependencies exact-pinned (gate-dep-pinning).
