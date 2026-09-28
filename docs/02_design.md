# RET-C2-108 — Design (`docs/02_design.md`)

**Template ID:** RET-C2-108
**Name:** RetailInteractionComplianceAuditAgent
**Category:** Cat 2 (RET)

- **L1 Base**: AgentBaseGraph (L1 direct inheritance — no L2 base agent, no `_invoke_impl`, no `.run()`)

> `VectorRAGAgent` (config `base_type`) names the KB-grounded Q&A **pattern** the agent follows;
> it is NOT a parent class. Under the AgentCore L1-direct policy the agent inherits
> `AgentBaseGraph` directly. The domain-specific compliance rule logic in `src/` (versioned KB +
> deterministic allergen/景品表示法/age checks + rule-based assessment) is what makes this Cat 2
> rather than a generic RAG agent.

---

## 1. Overview

RET-C2-108 audits a single retail staff–customer interaction transcript (floor microphones,
self-checkout, or call-center STT) for **regulatory compliance** — not general service-quality
coaching (that is a separate template). Given a transcript plus optional structured fields (staff ID,
interaction context, store/region, applicable compliance rule set), it retrieves the applicable
versioned KB rules, runs three deterministic checks (allergen-disclosure adequacy, 景品表示法 verbal
promotional-claim compliance, age-verification procedure adherence), and returns a rule-based
**COMPLIANT / NON_COMPLIANT / CONDITIONAL** compliance status with the specific non-compliant
quotes flagged (severity) and a manager remediation action. Every report cites the KB version +
as-of date (non-suppressible).

## 2. Architecture — 5-node backbone

The graph class **is** the agent (`RetailInteractionComplianceAuditAgent(AgentBaseGraph)`). The
fixed backbone is `initialize → pre_process → main → post_process → finalize`;
`super().register_nodes()` preserves the framework `initialize` + `finalize`, and the template
registers the three middle nodes.

| Slot | Node / file | Responsibility | Status out |
|---|---|---|---|
| pre_process | `PreProcessNode` (`src/nodes/pre_process_node.py`) | TranscriptNormalize + ContextExtract + **S-2 input gate** (`src/services/context_parse.py`): injection block, length bounds, interaction-context + rule-set constraints; build the compliance context | SUCCESS / ERROR |
| main | `MainNode` (`src/nodes/main_node.py`) | RuleRetrieve (`compliance_kb.py`) + AllergenDisclosureCheck / KeihinVerbalClaimCheck / AgeVerificationCheck (`compliance_check.py`) + AssessmentGenerate + render (`report_render.py`). Combined Main slot; non-suppressible `audit_generated` | SUCCESS / ERROR |
| post_process | `PostProcessNode` (`src/nodes/post_process_node.py`) | ReportValidate + **S-3 content gate** (`output_safety.py`): anti-suppression + mandatory KB-citation gate + secret redaction + injection blanking | SUCCESS / ERROR |

The architect's original node flow
`TranscriptIngest → SpeakerDiarize → ContextExtract → RuleRetrieve → AllergenDisclosureCheck →
KeihinVerbalClaimCheck → AgeVerificationCheck → AssessmentGenerate → ReportValidate` maps onto the
5-node backbone with no logic dropped: ingest+extract → pre_process (speaker diarization is an
upstream primitive consumed from a separate template, not reimplemented here); the
KB-retrieve/checks/assessment cluster → main; report validation + S-3 → post_process.

## 3. State (flat TypedDict — ADR-005)

`RET_C2_108_State(AgentState)` — primitives only; list/dict artifacts (`applied_rules`,
`check_results`, `flagged_quotes`, `remediation_action`, `audit_context`, `input_errors`) are
JSON-serialized as `Optional[str]` via `to_json`/`from_json` (msgpack-safe). Anti-suppression
invariant: `audit_generated` (default False, set True by main). S-3 flags: `citations_present`,
`redaction_triggered`.

## 4. Category & Agent-vs-Tool

Cat 2 by construction: multi-step pipeline completing one named job (regulatory compliance audit
of a staff interaction), with domain business logic baked into `src/` (versioned compliance-rule
KB, allergen-disclosure adequacy rubric, 景品表示法 verbal prohibited-claim list, age-verification
procedure check, severity + remediation composition). It holds `AgentState`, manages an injected
KB/LLM resource, applies non-suppressible security gates, and is independently deployable — not a
stateless pure function, so it is an Agent, not a Tool.

## 5. KB versioning

Retail interaction compliance enforcement is live and evolving (CAA allergen guidance 2026,
景品表示法 2026 verbal-claims extension), so the KB is versioned and updatable and every report
cites `kb_version` + `kb_as_of_date`. Production injects a versioned KB service via `config["kb"]`;
CI uses an offline `ComplianceKBStub` (`ret-interaction-compliance-2026.05.1`, 2026-05-01).

## 6. Security (5-layer, framework-enforced)

- **S-1** — every node declares `required_trust_level = TrustLevel.VERIFIED_EXTERNAL`.
- **S-2** — `context_parse.build_audit_context()` before any context is built.
- **S-3** — `output_safety.apply_output_safety()` in post_process (mandatory citation + redaction +
  injection) + anti-suppression on `audit_generated`.
- **S-4** — `emit_trace_event` domain events (`pre_process_complete`, `assessment_complete`,
  `post_process_complete`).
- **S-5** — no hardcoded secrets; `dependencies=[]`; exact-pinned dev deps + build-system.

## 7. Boundary (distinct siblings)

Regulatory compliance audit only. General 接客品質 performance coaching / service-phrase scoring /
upsell rating is a separate template — a disjoint deliverable coupled only by the shared STT-transcript
input contract (no inheritance, no composition). Multi-speaker diarization is a separate template, an
upstream primitive this agent consumes. Staff training voice is a separate template.

## 8. Open design item (PII / APPI)

Staff + customer interaction transcripts are personal data under APPI. Current scope: S-3 redacts
credential/secret patterns only. Deeper transcript de-identification — speaker isolation, scope of
customer-PII redaction, and the consent basis for recording/audit — is deferred to stage:design and
tracked in `docs/04_security_review.md`.
