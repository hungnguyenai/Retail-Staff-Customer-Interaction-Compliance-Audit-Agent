"""Integration test — full graph compile() + invoke() (Cat 2 backbone).

Drives the whole pipeline (initialize → pre_process → main → post_process → finalize) with
VERIFIED_EXTERNAL trust (pre_process requires it). Deterministic core — offline compliance-rule KB
stub, no live LLM. The query is passed as a JSON payload on user_input; a plain string is accepted
as the transcript.
"""

import json

import pytest

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets.inmemory_provider import InMemoryProvider

from src.graph.graph import RetailInteractionComplianceAuditAgent


def _external_ctx():
    return InvocationContext(
        correlation_id="it-corr",
        session_id="it-session",
        thread_id="it-thread",
        parent_trace_id="",
        caller_id="compliance-ops",
        caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
        secrets=InMemoryProvider({}),
        hitl_allowed=True,
    )


@pytest.fixture
def agent():
    a = RetailInteractionComplianceAuditAgent(config={"max_retry": 1})
    a.compile()
    return a


def test_full_pipeline_compliant(agent):
    payload = json.dumps(
        {
            "transcript": "いらっしゃいませ。ありがとうございました。",
            "staff_id": "S-001",
            "interaction_context": "checkout",
            "store_region": "tokyo",
            "output_language": "ja",
        }
    )
    with bound_secrets(InMemoryProvider({})):
        result = agent.invoke(payload, ctx=_external_ctx())
    assert result["status"] == "success"
    assert result["output"] is not None
    report = result["output"]["report"]
    assert "接客コンプラ監査結果" in report
    # S-3 citation gate ran — KB provenance present in the report.
    assert "ret-interaction-compliance-2026.05.1" in report
    assert result["output"]["citations_present"] is True
    assert "MainNode" in result["node_history"]


def test_full_pipeline_non_compliant_keihin(agent):
    payload = json.dumps(
        {
            "transcript": "こちらは業界最安値です。ビールもございます。年齢確認のボタンをお願いします。",
            "staff_id": "S-002",
            "interaction_context": "checkout",
        }
    )
    with bound_secrets(InMemoryProvider({})):
        result = agent.invoke(payload, ctx=_external_ctx())
    assert result["status"] == "success"
    assert "NON_COMPLIANT" in result["output"]["report"]


def test_full_pipeline_error_on_empty_input(agent):
    with bound_secrets(InMemoryProvider({})):
        result = agent.invoke("", ctx=_external_ctx())
    assert result["status"] in ("error", "cancelled")
