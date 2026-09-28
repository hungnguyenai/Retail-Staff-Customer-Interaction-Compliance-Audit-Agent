"""TranscriptNormalize + ContextExtract service — validate the audit query + build context.

Pure functions, no state. The S-2 input gate runs here before any compliance context is built:
  - transcript: non-empty, length-bounded, free of prompt-injection markers
  - staff_id / store_region: coerced to bounded strings (opaque identifiers, not credentials)
  - interaction_context: constrained to an allowed set (checkout / floor / phone / unknown)
  - rule_set: constrained to the known compliance dimensions (allergen / keihin / age);
    an empty / unknown set defaults to all three dimensions

`build_audit_context()` returns a `(context, errors)` tuple. `context` is None when the query
fails the gate (no usable transcript); `errors` is a list of `{"field","reason"}` dicts.
"""

from __future__ import annotations

from typing import Any

import re

_MAX_TEXT_LEN = 20000
_MAX_ID_LEN = 128
ALLOWED_CONTEXTS = {"checkout", "floor", "phone", "unknown"}
ALLOWED_RULES = {"allergen", "keihin", "age"}

# Prompt-injection markers — reject the value outright on match (S-2).
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+all\s+previous", re.IGNORECASE),
    re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"^\s*system\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"###\s*(system|assistant)\s*:", re.IGNORECASE),
]


def _has_injection(value: str) -> bool:
    return any(p.search(value) for p in _INJECTION_PATTERNS)


def _clean_id(value: Any, field: str, errors: list[dict[str, Any]]) -> str:
    text = str(value or "").strip()
    if len(text) > _MAX_ID_LEN:
        errors.append({"field": field, "reason": f"S-2: {field} too long — truncated"})
        text = text[:_MAX_ID_LEN]
    return text


def _clean_rule_set(value: Any, errors: list[dict[str, Any]]) -> list[str]:
    if value is None or value == "":
        return sorted(ALLOWED_RULES)
    if isinstance(value, str):
        items = [v.strip().lower() for v in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = [str(v).strip().lower() for v in value]
    else:
        errors.append({"field": "rule_set", "reason": "S-2: rule_set not a list/string — defaulted"})
        return sorted(ALLOWED_RULES)
    cleaned = [r for r in items if r in ALLOWED_RULES]
    for r in items:
        if r and r not in ALLOWED_RULES:
            errors.append({"field": "rule_set", "reason": f"S-2: unknown rule '{r}' — ignored"})
    return cleaned or sorted(ALLOWED_RULES)


def build_audit_context(
    transcript: Any,
    staff_id: Any = "",
    interaction_context: Any = "unknown",
    store_region: Any = "",
    rule_set: Any = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Validate the audit query (S-2) and build the compliance context.

    Returns `(context, errors)`. `context` is None if transcript is missing/rejected.
    """
    errors: list[dict[str, Any]] = []

    text = str(transcript or "").strip()
    if not text:
        return None, [{"field": "transcript", "reason": "S-2: transcript is required"}]
    if len(text) > _MAX_TEXT_LEN:
        errors.append({"field": "transcript", "reason": "S-2: transcript too long"})
        text = text[:_MAX_TEXT_LEN]
    if _has_injection(text):
        return None, [{"field": "transcript", "reason": "S-2: prompt-injection pattern blocked"}]

    staff_id_c = _clean_id(staff_id, "staff_id", errors)
    store_region_c = _clean_id(store_region, "store_region", errors)

    context_c = str(interaction_context or "unknown").strip().lower()
    if context_c not in ALLOWED_CONTEXTS:
        errors.append(
            {"field": "interaction_context", "reason": f"S-2: unknown context '{interaction_context}' — coerced"}
        )
        context_c = "unknown"

    rule_set_c = _clean_rule_set(rule_set, errors)

    context = {
        "transcript": text,
        "staff_id": staff_id_c,
        "interaction_context": context_c,
        "store_region": store_region_c,
        "rule_set": rule_set_c,
    }
    return context, errors
