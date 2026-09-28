"""Output safety (S-3 content gate, relocated to node logic).

The 5-layer security model is framework-enforced; there are no developer `_security_gate_*`
methods. The S-3 content checks are a pure function called by PostProcessNode after the compliance
report is rendered:

  1. Anti-suppression — the compliance assessment MUST have been generated (audit_generated).
     This is the non-suppressible invariant.
  2. CitationGate — the rendered report MUST cite the KB version + as-of date. This is
     MANDATORY and non-suppressible: a compliance report without provenance is not releasable.
  3. SecretLeakageGate — credential / private-IP patterns are redacted in place with [REDACTED].
     (Deep transcript PII/APPI de-identification is a stage:design item — see docs/04.)
  4. Injection markers — prompt-injection markers blank the output.

Always returns a dict with all keys:
{final_output, citations_present, redaction_triggered, error}
(error is None on the clean path).
"""

from __future__ import annotations

from typing import Any

import re

_REDACTION_PLACEHOLDER = "[REDACTED]"

# Secret-leakage redaction patterns (label kept for auditability).
_SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "openai-api-key"),
    (re.compile(r"AKIA[A-Z0-9]{16}"), "aws-access-key"),
    (re.compile(r"eyJ[a-zA-Z0-9._-]{10,}"), "jwt-token"),
    (re.compile(r"(?i)(password|api_key|token|secret)\s*=\s*[\"']?[^\s\"']{8,}[\"']?"), "credential-assignment"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}"), "bearer-token"),
    (re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "private-ip"),
    (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "private-ip"),
    (re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"), "private-ip"),
]

# Prompt-injection markers (blank the whole output on match).
_INJECTION_PATTERNS = [
    re.compile(r"<\|"),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"IGNORE\s+PREVIOUS\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"</s>"),
    re.compile(r"###\s*Human:|###\s*Assistant:", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>"),
]


def _has_citation(text: str, kb_version: str, kb_as_of_date: str) -> bool:
    """The report must carry both the KB version and the as-of date."""
    return bool(kb_version) and bool(kb_as_of_date) and kb_version in text and kb_as_of_date in text


def apply_output_safety(
    final_output: str, audit_generated: bool, kb_version: str, kb_as_of_date: str
) -> dict[str, Any]:
    """Apply the S-3 content checks to the rendered compliance report.

    Returns {final_output, citations_present, redaction_triggered, error}. The caller
    blanks/short-circuits based on a non-None `error` and emits the audit trace.
    """
    if not final_output:
        return {
            "final_output": final_output,
            "citations_present": False,
            "redaction_triggered": False,
            "error": "S-3 violation: empty compliance report output",
        }

    # 1. Anti-suppression: the compliance assessment must have been generated.
    if not audit_generated:
        return {
            "final_output": final_output,
            "citations_present": False,
            "redaction_triggered": False,
            "error": ("S-3 violation: audit_generated is False — the compliance assessment did not execute"),
        }

    # 2. CitationGate (MANDATORY) — provenance must be present.
    citations_present = _has_citation(final_output, kb_version, kb_as_of_date)
    if not citations_present:
        return {
            "final_output": final_output,
            "citations_present": False,
            "redaction_triggered": False,
            "error": ("S-3 violation: report missing KB version / as-of date citation (non-suppressible)"),
        }

    # 3. SecretLeakageGate: scan + redact credential / private-IP patterns in place.
    redaction_triggered = False
    for pattern, _label in _SECRET_PATTERNS:
        new_output, count = re.subn(pattern, _REDACTION_PLACEHOLDER, final_output)
        if count > 0:
            final_output = new_output
            redaction_triggered = True

    # 4. Injection marker check.
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(final_output):
            return {
                "final_output": "[REDACTED] — S-3: prompt injection marker in output",
                "citations_present": citations_present,
                "redaction_triggered": redaction_triggered,
                "error": "S-3 violation: injection marker in final_output — redacted",
            }

    return {
        "final_output": final_output,
        "citations_present": citations_present,
        "redaction_triggered": redaction_triggered,
        "error": None,
    }
