"""RET-C2-108 graph — AgentBaseGraph (L1 direct). The graph class IS the agent.

Cat 2 (multi-step pipeline completing one named job: audit a single retail staff–customer
interaction transcript for regulatory compliance — allergen-disclosure adequacy, 景品表示法 verbal
promotional claims, and age-verification procedure — and return a cited compliance report with
flagged non-compliant quotes + a manager remediation action). Fixed 5-node backbone
initialize → pre_process → main → post_process → finalize. No separate agent class, no double-graph,
no _invoke_impl, no .run(). Public entry: Graph(config).compile() then .invoke(user_input, ctx=...).
The 5-layer security model is framework-enforced — there are no developer `_security_gate_*`
methods (S-2 input gate lives in pre_process, S-3 citation gate + output safety in post_process as
ordinary node logic).

Scope: regulatory compliance audit only. General 接客品質 performance coaching is out of scope and
owned by a separate template; this agent produces no coaching score. The domain-specific compliance
rule logic in src/ (allergen / 景品表示法 / age rules + severity + remediation) is what makes this
Cat 2 rather than a generic RAG — the agent inherits AgentBaseGraph directly (L1-direct policy).
"""

from __future__ import annotations

from typing import Any

from framework.graph.agent_base_graph import AgentBaseGraph

from src.nodes.main_node import MainNode
from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import RET_C2_108_State


class RetailInteractionComplianceAuditAgent(AgentBaseGraph):
    """RET-C2-108 — Retail Staff Interaction Compliance Audit Agent (Cat 2)."""

    @property
    def name(self) -> str:
        return "ret-c2-108"

    @property
    def state_schema(self) -> type[RET_C2_108_State]:
        return RET_C2_108_State

    def register_nodes(self) -> None:
        super().register_nodes()  # preserve default initialize + finalize backbone
        cfg = self.config if hasattr(self, "config") else {}
        kb = cfg.get("kb")  # injected versioned compliance-rule KB service; None → offline stub
        llm = cfg.get("llm")
        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = MainNode(kb=kb, llm=llm)
        self._nodes["post_process"] = PostProcessNode()


# Alias for the AgentRegistry entry point (config/agent.yaml module: "src.graph").
Graph = RetailInteractionComplianceAuditAgent


def build_agent(config: dict[str, Any] | None = None) -> RetailInteractionComplianceAuditAgent:
    """Factory for AgentRegistry entry point."""
    return RetailInteractionComplianceAuditAgent(config=config or {})
