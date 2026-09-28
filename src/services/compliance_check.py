"""Compliance checks + assessment — the analytical core of the main pipeline.

Pure, deterministic functions (no state, no LLM required): AllergenDisclosureCheck,
KeihinVerbalClaimCheck, AgeVerificationCheck, then AssessmentGenerate. An optional LLM may be
injected to narrate the assessment rationale, but the per-dimension COMPLIANT / NON_COMPLIANT /
CONDITIONAL decision itself is rule-based (keyword / marker heuristics over the transcript) so the
output is auditable and reproducible in CI.

Each check returns {"check","result","detail","quote","severity"} where result is
PASS / FAIL / CONDITIONAL / SKIP. The overall compliance status is the worst outcome across the
applied checks:
  any FAIL        -> NON_COMPLIANT
  any CONDITIONAL -> CONDITIONAL
  else            -> COMPLIANT
"""

from __future__ import annotations

from typing import Any

import re

from src.services.compliance_kb import get_rule

# --- marker vocabularies (deterministic heuristics over the transcript) ---

_ALLERGEN_INQUIRY = [
    "アレルギー",
    "アレルゲン",
    "allerg",
    "アレル",
]
_ALLERGEN_ADEQUATE = [
    "原材料",
    "成分",
    "表示",
    "ラベル",
    "確認いたし",
    "お調べ",
    "調べ",
    "確認します",
    "ingredient",
    "label",
    "let me check",
    "will check",
]
_ALLERGEN_REASSURE = [
    "大丈夫",
    "たぶん",
    "多分",
    "平気",
    "probably fine",
    "probably ok",
    "should be fine",
]

_KEIHIN_CLAIMS = [
    "最安値",
    "業界一",
    "業界No",
    "日本一",
    "世界一",
    "ナンバーワン",
    "no.1",
    "no. 1",
    "絶対",
    "必ず効",
    "100%効",
    "最高級",
    "world's best",
    "cheapest",
    "guaranteed",
]

_AGE_ITEMS = [
    "酒",
    "ビール",
    "日本酒",
    "ワイン",
    "ウイスキー",
    "たばこ",
    "タバコ",
    "煙草",
    "alcohol",
    "beer",
    "wine",
    "cigarette",
    "tobacco",
]
_AGE_VERIFY = [
    "年齢確認",
    "20歳",
    "二十歳",
    "成人",
    "ボタン",
    "タッチ",
    "身分証",
    "免許",
    "age verification",
    "over 20",
    "id check",
    "verify",
]


def _segments(text: str) -> list[str]:
    """Split the transcript into short segments for quote extraction."""
    raw = re.split(r"[\n。.!?！？]+", text)
    return [s.strip() for s in raw if s.strip()]


def _find_quote(text: str, markers: list[str]) -> str | None:
    """Return the first transcript segment containing any marker (case-insensitive)."""
    lowered_markers = [m.lower() for m in markers]
    for seg in _segments(text):
        low = seg.lower()
        if any(m in low for m in lowered_markers):
            return seg[:300]
    return None


def _contains(text: str, markers: list[str]) -> bool:
    low = text.lower()
    return any(m.lower() in low for m in markers)


def check_allergen_disclosure(context: dict[str, Any]) -> dict[str, Any]:
    """A1 — an allergen concern must be met with an adequate disclosure, not a bare reassurance."""
    text = context.get("transcript", "")
    sev = get_rule("A1").get("severity", "high")
    if not _contains(text, _ALLERGEN_INQUIRY):
        return {
            "check": "A1",
            "result": "SKIP",
            "detail": "no allergen inquiry in transcript",
            "quote": None,
            "severity": sev,
        }
    if _contains(text, _ALLERGEN_ADEQUATE):
        return {
            "check": "A1",
            "result": "PASS",
            "detail": "allergen inquiry met with an adequate disclosure (ingredient/label/check)",
            "quote": None,
            "severity": sev,
        }
    if _contains(text, _ALLERGEN_REASSURE):
        return {
            "check": "A1",
            "result": "FAIL",
            "detail": (
                "allergen inquiry answered with an unqualified reassurance instead of an "
                "adequate disclosure (A1 / CAA allergen guidance 2026)"
            ),
            "quote": _find_quote(text, _ALLERGEN_REASSURE),
            "severity": sev,
        }
    return {
        "check": "A1",
        "result": "CONDITIONAL",
        "detail": (
            "allergen inquiry present but no clear adequate disclosure detected; confirm "
            "staff pointed to ingredient labelling or deferred to a check (A1)"
        ),
        "quote": _find_quote(text, _ALLERGEN_INQUIRY),
        "severity": sev,
    }


def check_keihin_verbal_claim(context: dict[str, Any]) -> dict[str, Any]:
    """KH1 — unsubstantiated verbal superlative/absolute claims are in 景品表示法 scope."""
    text = context.get("transcript", "")
    sev = get_rule("KH1").get("severity", "medium")
    if _contains(text, _KEIHIN_CLAIMS):
        return {
            "check": "KH1",
            "result": "FAIL",
            "detail": (
                "unsubstantiated superlative / absolute verbal promotional claim at "
                "checkout — in scope of the 景品表示法 2026 verbal-claims extension (KH1)"
            ),
            "quote": _find_quote(text, _KEIHIN_CLAIMS),
            "severity": sev,
        }
    return {
        "check": "KH1",
        "result": "PASS",
        "detail": "no unsubstantiated superlative / absolute verbal promotional claim detected",
        "quote": None,
        "severity": sev,
    }


def check_age_verification(context: dict[str, Any]) -> dict[str, Any]:
    """AV1 — age-restricted sales require an age-verification step."""
    text = context.get("transcript", "")
    sev = get_rule("AV1").get("severity", "high")
    if not _contains(text, _AGE_ITEMS):
        return {
            "check": "AV1",
            "result": "SKIP",
            "detail": "no age-restricted item in transcript",
            "quote": None,
            "severity": sev,
        }
    if _contains(text, _AGE_VERIFY):
        return {
            "check": "AV1",
            "result": "PASS",
            "detail": "age-restricted item sold with an age-verification step present",
            "quote": None,
            "severity": sev,
        }
    return {
        "check": "AV1",
        "result": "FAIL",
        "detail": (
            "age-restricted item sold without a detected age-verification step "
            "(年齢確認 / touch-panel confirmation) — AV1"
        ),
        "quote": _find_quote(text, _AGE_ITEMS),
        "severity": sev,
    }


_CHECK_BY_DIM = {
    "allergen": check_allergen_disclosure,
    "keihin": check_keihin_verbal_claim,
    "age": check_age_verification,
}


def run_checks(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Run every check selected by the context's rule_set; keep SKIP for transparency."""
    dims = context.get("rule_set") or list(_CHECK_BY_DIM.keys())
    results: list[dict[str, Any]] = []
    for dim in dims:
        fn = _CHECK_BY_DIM.get(dim)
        if fn is not None:
            results.append(fn(context))
    return results


def generate_assessment(check_results: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Combine check results into (compliance_status, flagged_quotes, remediation_actions).

    Deterministic — status is the worst outcome, flagged_quotes carry the offending quote +
    severity, remediation lists the manager action per flagged dimension.
    """
    active = [c for c in check_results if c["result"] != "SKIP"]
    if not active:
        return "UNKNOWN", [], ["insufficient information to assess interaction compliance"]

    flagged_quotes: list[dict[str, Any]] = []
    remediation: list[str] = []
    has_fail = any(c["result"] == "FAIL" for c in active)
    has_conditional = any(c["result"] == "CONDITIONAL" for c in active)

    for c in active:
        if c["result"] in ("FAIL", "CONDITIONAL"):
            if c.get("quote"):
                flagged_quotes.append(
                    {"rule": c["check"], "quote": c["quote"], "severity": c.get("severity", "medium")}
                )
            prefix = "confirm: " if c["result"] == "CONDITIONAL" else ""
            remediation.append(f"[{c['check']}] {prefix}{c['detail']}")

    if has_fail:
        return "NON_COMPLIANT", flagged_quotes, remediation
    if has_conditional:
        return "CONDITIONAL", flagged_quotes, remediation
    return "COMPLIANT", [], []


def assessment_coverage(
    check_results: list[dict[str, Any]],
    applied_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """How much of the declared rule set actually produced a judgement.

    generate_assessment drops SKIP results before deciding, which is correct -- a rule with
    no applicable evidence should not vote. What was missing is that the caller never learned
    how many rules stayed silent, so a pass resting on one rule out of three was published
    with the same confidence as a pass across all three.

    `partial` is True when at least one rule was evaluated and at least one was not.
    """
    evaluated = [c["check"] for c in check_results if c.get("result") != "SKIP"]
    skipped = [
        {"check": c["check"], "reason": c.get("detail", "not applicable to this interaction")}
        for c in check_results
        if c.get("result") == "SKIP"
    ]
    declared = [str(r.get("rule_id") or "") for r in (applied_rules or [])]
    return {
        "evaluated": evaluated,
        "skipped": skipped,
        "evaluated_count": len(evaluated),
        "checked_count": len(check_results),
        "declared_rules": [d for d in declared if d],
        "partial": bool(evaluated) and bool(skipped),
    }
