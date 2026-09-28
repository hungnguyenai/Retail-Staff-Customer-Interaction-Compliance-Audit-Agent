"""RuleRetrieve service — versioned retail staff-interaction compliance-rule knowledge base.

The KB is VERSIONED and updatable: retail interaction compliance is live and evolving — the
CAA 2026 allergen-at-point-of-sale expectations and the 景品表示法 2026 extension of enforcement
to verbal promotional claims at checkout are in force — so compliance reports MUST cite the KB
version + as-of date. Here the KB is an offline, deterministic dict so CI is fully testable
without a live KB store; in production a versioned KB service is injected via config
(`config["kb"]`) and its `version` / `as_of_date` / `applicable_rules()` API replaces this stub.

Rule scope (docs/02_design.md KB):
  - A1   Allergen-disclosure adequacy — when a customer raises an allergen concern, staff must
         give an adequate disclosure response (confirm ingredients / point to labelling / defer to
         a check) rather than an unqualified reassurance. (CAA allergen guidance 2026.)
  - KH1  景品表示法 verbal promotional-claim compliance — unsubstantiated superlative / absolute
         verbal claims ("最安値", "日本一", "絶対に効く", "No.1") at checkout are in scope of the
         2026 verbal-claims extension.
  - AV1  Age-verification procedure adherence — for age-restricted items (酒 / タバコ), staff must
         perform an age-verification step (年齢確認 prompt / touch-panel confirmation).
"""

from __future__ import annotations

from typing import Any

KB_VERSION = "ret-interaction-compliance-2026.05.1"
KB_AS_OF_DATE = "2026-05-01"

_RULES = {
    "A1": {
        "rule_id": "A1",
        "title": "アレルゲン開示の適切性 (CAA allergen guidance 2026)",
        "summary": (
            "When a customer raises an allergen concern, staff must give an adequate disclosure "
            "response — confirm ingredients, point to the labelling, or defer to a check — rather "
            "than an unqualified reassurance such as 'probably fine'."
        ),
        "severity": "high",
    },
    "KH1": {
        "rule_id": "KH1",
        "title": "景品表示法 口頭プロモーション表示 (2026 verbal-claims extension)",
        "summary": (
            "Unsubstantiated superlative / absolute verbal promotional claims at checkout — e.g. "
            "'業界最安値', '日本一', '絶対に効く', 'No.1' — are within scope of the 2026 extension of "
            "景品表示法 enforcement to verbal claims and must be substantiated."
        ),
        "severity": "medium",
    },
    "AV1": {
        "rule_id": "AV1",
        "title": "年齢確認手続きの遵守 (age-restricted items)",
        "summary": (
            "For age-restricted items (alcohol / tobacco), staff must perform an age-verification "
            "step (年齢確認 prompt or touch-panel confirmation) before completing the sale."
        ),
        "severity": "high",
    },
}

# Map a compliance dimension name (rule_set token) to its rule_id.
_DIM_TO_RULE = {"allergen": "A1", "keihin": "KH1", "age": "AV1"}


class ComplianceKBStub:
    """Deterministic offline stand-in for the versioned compliance-rule KB (CI / tests)."""

    version = KB_VERSION
    as_of_date = KB_AS_OF_DATE

    def applicable_rules(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return applicable_rules(context)


def applicable_rules(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Select the KB rules applicable to this audit context (driven by rule_set)."""
    dims = context.get("rule_set") or list(_DIM_TO_RULE.keys())
    rules: list[dict[str, Any]] = []
    for dim in dims:
        rule_id = _DIM_TO_RULE.get(dim)
        if rule_id and rule_id in _RULES and _RULES[rule_id] not in rules:
            rules.append(_RULES[rule_id])
    if not rules:
        # Always cite at least the allergen rule so a report is never rule-less.
        rules.append(_RULES["A1"])
    return rules


def get_rule(rule_id: str) -> dict[str, Any]:
    return _RULES.get(rule_id, {})
