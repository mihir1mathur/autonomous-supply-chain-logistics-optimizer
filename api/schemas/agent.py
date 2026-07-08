"""
============================================================================
AGENT SCHEMAS  (Week 7)   endpoints: /agents/*
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE HOLDS
--------------------
  The Pydantic REQUEST and RESPONSE schemas for the Week 7 AI ORCHESTRATION
  endpoints (decide, simulate, status). Same idea as the Week 4 entity schemas,
  the Week 5 optimization schemas and the Week 6 execution schemas: the request
  schema validates/shapes the JSON coming in, and the response schema controls
  exactly what goes out.

THE REQUEST IS INTENTIONALLY FORGIVING
--------------------------------------
  The whole point of the orchestration layer is that a user can describe what
  they want in plain words. So the ONLY thing that really matters is `goal` (a
  free-text description). Every other field is an OPTIONAL override that lets a
  caller pin down a specific optimizer / scenario / warehouse / constraint if
  they already know it. `POST /agents/decide` with `{"goal": "..."}` is enough;
  `{}` runs a sensible default decision. This mirrors the Week 5/6 "empty body
  works" convention.

THE RESPONSE MIRRORS THE OrchestrationResult
--------------------------------------------
  The nested pieces (plan, scenario, optimization, evaluation, report, trace)
  are returned as flexible dicts - exactly as the Week 6 OptimizationRunResponse
  returns metrics/evaluation/details as dicts - because they are already
  well-structured JSON built by the agents, and typing every nested field again
  would only duplicate the dataclasses in agents/utils.py.
============================================================================
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ===========================================================================
# REQUEST
# ===========================================================================
class AgentDecisionRequest(BaseModel):
    """Ask the agent crew to make one autonomous optimization decision."""

    goal: str | None = Field(
        None,
        description="Plain-language description of what you want (e.g. 'optimize "
        "deliveries for a holiday peak, we are short on vans'). The Planner and "
        "Scenario agents infer the optimizer and scenario from this.",
    )
    # ---- Optional explicit overrides (used as-is when provided) ------------
    optimizer: str | None = Field(
        None, description="Force the optimizer: assignment / fleet / routes / warehouse."
    )
    scenario: str | None = Field(
        None, description="Force the scenario (see GET /optimization/scenarios)."
    )
    warehouse_id: str | None = Field(None, description="Target warehouse (else auto-selected).")
    priority: str | None = Field(None, description="Force the priority: normal / high.")
    # ---- Optional constraints forwarded to the execution service -----------
    max_shipments: int | None = Field(None, ge=1, description="Cap on shipments to include.")
    max_stops: int | None = Field(None, ge=1, description="Cap on route stops (routes optimizer).")
    sample_size: int | None = Field(None, ge=1, description="Demands to sample (warehouse optimizer).")
    strategy: str | None = Field(None, description="Routing strategy (routes optimizer).")
    reserve_inventory: bool | None = Field(
        None, description="Warehouse optimizer: reserve stock as it is promised."
    )
    # ---- Orchestration controls -------------------------------------------
    benchmark: bool = Field(
        True, description="Let the Evaluation agent compare a stressed scenario to 'normal'."
    )


# ===========================================================================
# RESPONSES
# ===========================================================================
class AgentDecisionResponse(BaseModel):
    """
    The full outcome of one autonomous decision: every agent's structured
    output, the execution trace, the orchestration mode, and (in CrewAI mode)
    the LLM narrative. Mirrors agents.utils.OrchestrationResult.
    """

    request: dict = {}
    mode: str
    mode_detail: str = ""
    success: bool
    message: str = ""
    plan: dict = {}
    scenario: dict = {}
    optimization: dict = {}
    evaluation: dict = {}
    report: dict = {}
    trace: dict = {}
    crew_narrative: str | None = None


class AgentStatusResponse(BaseModel):
    """A quick description of the orchestration layer (GET /agents/status)."""

    orchestration_mode: str
    mode_detail: str
    crewai_installed: bool
    llm_provider: str
    llm_model: str
    agents: list[str]
    optimizers: list[str]
