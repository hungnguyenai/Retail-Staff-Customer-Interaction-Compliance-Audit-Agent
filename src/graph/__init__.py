"""src.graph package — re-export the agent class so AgentRegistry resolves
`module: "src.graph"` + `class: "RetailInteractionComplianceAuditAgent"` via the package namespace.
"""

from src.graph.graph import (
    Graph,
    RetailInteractionComplianceAuditAgent,
    build_agent,
)

__all__ = ["Graph", "RetailInteractionComplianceAuditAgent", "build_agent"]
