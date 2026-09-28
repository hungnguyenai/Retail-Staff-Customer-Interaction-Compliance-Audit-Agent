"""Proof-of-Boundary — S-3 output gate + anti-suppression + citation gate (PB-03..PB-05).

PostProcessNode must hard-fail when the assessment was suppressed; the S-3 service must enforce the
MANDATORY KB-provenance citation (kb_version + as-of date) and redact secret patterns. Note: the
framework's AgentStatus has SUCCESS / ERROR (no COMPLETE) — a clean post_process returns SUCCESS.
"""

from framework.schemas.agent_status import AgentStatus

from src.nodes.post_process_node import PostProcessNode
from src.services.output_safety import apply_output_safety

_KB_VER = "ret-interaction-compliance-2026.05.1"
_KB_DATE = "2026-05-01"


def _cited(body: str) -> str:
    return f"{body}\n> Source: compliance KB `{_KB_VER}` (as of {_KB_DATE})."


# --- PB-03 — S-3: audit_generated anti-suppression ---


def test_anti_suppression_error_when_audit_false():
    """PostProcessNode must return ERROR if audit_generated is False."""
    result = PostProcessNode().execute(
        {
            "final_output": _cited("Status: COMPLIANT"),
            "audit_generated": False,  # suppressed — must be blocked
            "kb_version": _KB_VER,
            "kb_as_of_date": _KB_DATE,
        }
    )
    assert result["status"] == AgentStatus.ERROR


def test_anti_suppression_passes_when_audit_true():
    """PostProcessNode must proceed (SUCCESS) if audit_generated is True and cited."""
    result = PostProcessNode().execute(
        {
            "final_output": _cited("Status: COMPLIANT"),
            "audit_generated": True,
            "kb_version": _KB_VER,
            "kb_as_of_date": _KB_DATE,
        }
    )
    assert result["status"] == AgentStatus.SUCCESS
    assert result["citations_present"] is True


# --- PB-04 — S-3: MANDATORY citation gate ---


def test_missing_citation_blocked():
    """S-3 must block a report that lacks the KB version / as-of date citation."""
    result = apply_output_safety(
        "Status: COMPLIANT (no provenance)",
        audit_generated=True,
        kb_version=_KB_VER,
        kb_as_of_date=_KB_DATE,
    )
    assert result["citations_present"] is False
    assert result["error"] is not None


def test_present_citation_passes():
    """S-3 must pass a report carrying both the KB version and as-of date."""
    result = apply_output_safety(
        _cited("Status: CONDITIONAL"),
        audit_generated=True,
        kb_version=_KB_VER,
        kb_as_of_date=_KB_DATE,
    )
    assert result["citations_present"] is True
    assert result["error"] is None


# --- PB-05 — S-3: secret-leakage redaction ---


def test_api_key_redacted_in_output():
    """S-3 must redact API key patterns in final_output."""
    text = _cited("Report leaked sk-abcdef1234567890abcdef1234567890 in a note.")
    result = apply_output_safety(
        text,
        audit_generated=True,
        kb_version=_KB_VER,
        kb_as_of_date=_KB_DATE,
    )
    assert "sk-" not in result["final_output"]
    assert result["redaction_triggered"] is True
    assert "[REDACTED]" in result["final_output"]
