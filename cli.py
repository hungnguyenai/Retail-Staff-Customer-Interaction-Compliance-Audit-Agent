"""AGENTIC STAR Marketplace entrypoint — one-shot Pod process.

Duoc Dockerfile goi qua CMD ["python", "cli.py"]. Compile agent, cap secrets,
roi ban giao cho shared.bootstrap.marketplace_app lo vong doi Marketplace.

Lop duoi day PHAI khop `class:` trong config/agent.yaml. Ban mac dinh cua bo
deploy hard-code `Graph`, nen repo nao co lop ten khac se ImportError ngay khi
container start — build, push va dang ky deu van xanh.
"""

from src.graph.graph import RetailInteractionComplianceAuditAgent
from shared.bootstrap.marketplace_app import run_agent_marketplace

if __name__ == "__main__":
    run_agent_marketplace(
        RetailInteractionComplianceAuditAgent,
        agent_name="ret_c2_108",
        namespace="ret-c2-108",
    )
