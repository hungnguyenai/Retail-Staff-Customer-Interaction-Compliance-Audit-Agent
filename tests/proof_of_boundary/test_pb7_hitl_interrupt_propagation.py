"""PB-7 — HITL interrupt propagation (structural scaffold placeholder).

RET-C2-108 has no HITL HOLD gate (`hitl.enabled` is absent/false — it produces a read-only
compliance-audit assessment for a human compliance reviewer; no action is executed by the agent,
so there is no in-graph approval interrupt). This placeholder exists so the scaffold always
carries a PB-7 test file; skip-guarded until/unless HITL is enabled for this template.
"""

import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("HITL_ENABLED"),
    reason="HITL not enabled for RET-C2-108 (read-only compliance audit; no HOLD gate)",
)


def test_hitl_interrupt_propagates():
    pytest.skip("RET-C2-108 has no HITL HOLD gate — nothing to propagate")
