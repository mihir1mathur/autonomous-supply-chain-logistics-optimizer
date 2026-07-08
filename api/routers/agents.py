"""
============================================================================
AGENT ORCHESTRATION ROUTER  (Week 7)   URL prefix: /agents
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for the Week 7 AI MULTI-AGENT ORCHESTRATION layer. THIN, exactly
like the Week 4 entity routers, the Week 5 optimization router and the Week 6
execution router: each endpoint reads the request, calls one method on a
service, and returns the result. No business logic and no database access live
here.

  POST /agents/decide     make one autonomous decision and STORE the run
  POST /agents/simulate   the same, but a throwaway what-if (not stored)
  GET  /agents/status     describe the orchestration layer (mode, agents, LLM)

WHY A NEW /agents PREFIX
  Week 5 owns /optimize/* (raw solvers); Week 6 owns /optimization/* (the
  execution layer). Week 7 adds a DISTINCT /agents/* namespace for the AI layer
  that ORCHESTRATES the execution layer. Keeping the prefixes separate means
  every earlier week is untouched and the concerns never collide.

WHY /decide RETURNS 200 EVEN ON A PARTIAL FAILURE
  An autonomous decision ALWAYS produces an auditable trace and (usually) a
  report, even if an agent could not complete. So this endpoint returns 200 with
  the full result and a `success` flag + `message`, rather than a bare 4xx - the
  caller reads `success` and inspects `trace` to see exactly what happened. (Bad
  JSON in the body is still a clean 422 via the Week 4 validation handler.)
============================================================================
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas.agent import (
    AgentDecisionRequest,
    AgentDecisionResponse,
    AgentStatusResponse,
)
from api.services.agent_service import agent_service

router = APIRouter(prefix="/agents", tags=["AI Orchestration"])


# ===========================================================================
# STATUS  (literal path, no database)
# ===========================================================================
@router.get(
    "/status",
    response_model=AgentStatusResponse,
    summary="Describe the AI orchestration layer (mode, agents, configured LLM)",
)
def agent_status():
    """Return the current orchestration mode, the agents, and the LLM settings."""
    return agent_service.status()


# ===========================================================================
# DECIDE / SIMULATE
# ===========================================================================
@router.post(
    "/decide",
    response_model=AgentDecisionResponse,
    summary="Make one autonomous optimization decision (plan -> scenario -> run -> evaluate -> report) and store it",
)
def agent_decide(
    payload: AgentDecisionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Drive the five-agent crew end to end, storing the optimization run."""
    req = payload or AgentDecisionRequest()
    return agent_service.decide(db, req.model_dump(), persist=True)


@router.post(
    "/simulate",
    response_model=AgentDecisionResponse,
    summary="Make one autonomous decision as a what-if, WITHOUT storing the run",
)
def agent_simulate(
    payload: AgentDecisionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Run exactly like /decide, but do not save the optimization to the history."""
    req = payload or AgentDecisionRequest()
    return agent_service.decide(db, req.model_dump(), persist=False)
