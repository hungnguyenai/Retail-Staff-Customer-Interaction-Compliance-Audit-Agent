"""Standalone HTTP entry point for RET-C2-108.

Entry points are adapters only — no business logic here. Secrets are provisioned once at
startup (provision_secrets) and bound per-request via bound_secrets (S-3); the agent and its
nodes never read process environment variables for secrets. For platform-level routing,
AgentGateway calls agent.invoke() directly.
"""

from typing import Any, cast
import os
import secrets
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets import factory as secrets_factory

from src.graph.graph import Graph

app = FastAPI(title="RET-C2-108 — Retail Staff Interaction Compliance Audit Agent")

agent = Graph()
agent.compile()
agent.provision_secrets(secrets_factory(namespace="ret-c2-108", agent_name="ret-c2-108"))


class InvokeRequest(BaseModel):
    input: str
    session_id: str = ""


@app.post("/invoke")
async def invoke(req: InvokeRequest, request: Request) -> dict[str, Any]:
    trust = getattr(request.state, "trust_level", TrustLevel.ANONYMOUS)
    # Standalone caller auth: when
    # INVOKE_AUTH_TOKEN is set on the server environment, callers that no upstream
    # middleware vouched for (still ANONYMOUS) must present it as a Bearer token
    # and run at VERIFIED_EXTERNAL. Middleware-established trust is never demoted.
    expected = os.environ.get("INVOKE_AUTH_TOKEN")
    if expected and trust is TrustLevel.ANONYMOUS:
        supplied = request.headers.get("authorization", "")
        if not secrets.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
            raise HTTPException(status_code=401, detail="Token is invalid or expired.")
        trust = TrustLevel.VERIFIED_EXTERNAL

    with bound_secrets(agent._secrets_provider):
        ctx = InvocationContext(
            session_id=req.session_id or str(uuid4()),
            # Runtime-provided transcripts are external-trust (S-1: pre_process requires VERIFIED_EXTERNAL).
            caller_trust_level=trust,
            caller_id=getattr(request.state, "caller_id", ""),
        )
        # invoke() comes from a wheel with no py.typed marker, so mypy sees Any.
        return cast(dict[str, Any], agent.invoke(req.input, ctx=ctx))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "ret-c2-108"}
