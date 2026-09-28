"""Proof-of-Boundary — invoke / security-gate order (PB-08).

The 5-layer security model depends on the nodes running in the fixed backbone order
initialize → pre_process → main → post_process → finalize. This boundary proof drives the full
graph and asserts, via `node_history`, that:

  1. the S-2 input gate (PreProcessNode) runs BEFORE the main capability (MainNode), and
  2. the mandatory S-3 output gate / citation check (PostProcessNode) runs AFTER main —
     so no compliance report is emitted before the citation gate has had a chance to run.

It also asserts the S-1 trust gate is enforced on the boundary node before any work happens
(an ANONYMOUS caller is refused).
"""

import json

import pytest

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets.inmemory_provider import InMemoryProvider

from src.graph.graph import RetailInteractionComplianceAuditAgent


def _ctx(trust=TrustLevel.VERIFIED_EXTERNAL):
    return InvocationContext(
        correlation_id="pb-corr",
        session_id="pb-session",
        thread_id="pb-thread",
        parent_trace_id="",
        caller_id="compliance-ops",
        caller_trust_level=trust,
        secrets=InMemoryProvider({}),
        hitl_allowed=True,
    )


def _payload():
    return json.dumps(
        {
            "transcript": "こちらは業界最安値です。卵アレルギーが心配です。大丈夫だと思います。",
            "staff_id": "S-010",
            "interaction_context": "checkout",
            "output_language": "ja",
        }
    )


@pytest.fixture
def agent():
    a = RetailInteractionComplianceAuditAgent(config={"max_retry": 1})
    a.compile()
    return a


def test_gate_order_pre_before_main_before_post(agent):
    """node_history must show PreProcessNode (S-2) → MainNode → PostProcessNode (S-3)."""
    with bound_secrets(InMemoryProvider({})):
        result = agent.invoke(_payload(), ctx=_ctx())
    assert result["status"] == "success"
    history = result["node_history"]
    for name in ("PreProcessNode", "MainNode", "PostProcessNode"):
        assert name in history, f"{name} missing from node_history: {history}"
    i_pre = history.index("PreProcessNode")
    i_main = history.index("MainNode")
    i_post = history.index("PostProcessNode")
    # S-2 before capability, S-3 after capability — the ordering the security model relies on.
    assert i_pre < i_main < i_post, f"unexpected node order: {history}"


def test_s1_trust_gate_precedes_work(agent):
    """An ANONYMOUS caller must be refused by the S-1 gate (no successful run)."""
    with bound_secrets(InMemoryProvider({})):
        result = agent.invoke(_payload(), ctx=_ctx(trust=TrustLevel.ANONYMOUS))
    assert result["status"] in ("error", "cancelled")


def test_output_only_after_citation_gate(agent):
    """A successful invoke must carry the S-3 citation report — output never bypasses it."""
    with bound_secrets(InMemoryProvider({})):
        result = agent.invoke(_payload(), ctx=_ctx())
    assert result["status"] == "success"
    assert result["output"]["citations_present"] is True
    assert "ret-interaction-compliance-2026.05.1" in result["output"]["report"]
