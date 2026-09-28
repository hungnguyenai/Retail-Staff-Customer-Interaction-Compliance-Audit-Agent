"""Security tests — S-1 trust gate (framework-enforced via __call__).

PreProcessNode declares required_trust_level = VERIFIED_EXTERNAL (runtime transcripts are
external-trust). The trust gate lives in BaseNode.__call__(), so we call node(state) (NOT
node.execute). The framework normalizes status to its string value after the gate.
"""

from framework.schemas.trust_level import TrustLevel

from src.nodes.pre_process_node import PreProcessNode


def _state(trust):
    return {
        "user_input": "",
        "transcript": "いらっしゃいませ。ありがとうございました。",
        "staff_id": "S-001",
        "interaction_context": "checkout",
        "store_region": "tokyo",
        "correlation_id": "x",
        "session_id": "x",
        "thread_id": "x",
        "trace_id": "",
        "caller_trust_level": trust,
        "caller_id": "",
        "hitl_allowed": True,
    }


def test_trust_gate_blocks_anonymous():
    result = PreProcessNode()(_state(TrustLevel.ANONYMOUS.value))
    assert result["status"] == "error"


def test_trust_gate_allows_verified_external():
    result = PreProcessNode()(_state(TrustLevel.VERIFIED_EXTERNAL.value))
    assert result["status"] == "success"


def test_trust_gate_allows_internal():
    # INTERNAL is higher trust than the required VERIFIED_EXTERNAL → allowed.
    result = PreProcessNode()(_state(TrustLevel.INTERNAL.value))
    assert result["status"] == "success"


def test_required_trust_level_is_valid_enum():
    # criterion #13 — must be one of the three valid enum values.
    assert PreProcessNode.required_trust_level in (
        TrustLevel.ANONYMOUS,
        TrustLevel.VERIFIED_EXTERNAL,
        TrustLevel.INTERNAL,
    )
