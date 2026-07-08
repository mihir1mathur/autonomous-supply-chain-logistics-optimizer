"""
============================================================================
AGENT ORCHESTRATION SERVICE  (Week 7)   -- FastAPI's bridge to the crew
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS SERVICE IS
--------------------
  The thin layer that sits between the FastAPI router and the Week 7 agent
  COORDINATOR. In the Week 7 architecture -

      User -> FastAPI -> Execution Service -> Coordinator -> agents -> ...

  - this is the "Execution Service" seam for the agent layer: the router stays
  HTTP-only (the Week 4 golden rule), and this service turns the validated
  request into a coordinator call, passing the request's database session
  straight through so every optimization the agents drive runs on the same
  session as the rest of the request.

WHY IT IS SO SMALL
------------------
  All the real work already lives in the agents package (planning, scenario
  choice, driving the execution service, evaluating, reporting) and in the Week
  6 execution service the agents call. This service just marshals the HTTP
  request into the coordinator's `request` dict, chooses persist vs simulate,
  and returns the coordinator's result as a plain dict. No business logic and no
  optimization code is duplicated here.
============================================================================
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from agents.config import crewai_installed, get_agent_settings, mode_explanation, orchestration_mode
from agents.coordinator import coordinator
from agents.planner_agent import VALID_OPTIMIZERS

# The free-form fields the request carries into the coordinator's request dict.
# (The coordinator/agents read whatever they recognise and ignore the rest.)
_REQUEST_FIELDS = (
    "goal",
    "optimizer",
    "scenario",
    "warehouse_id",
    "priority",
    "max_shipments",
    "max_stops",
    "sample_size",
    "strategy",
    "reserve_inventory",
)


class AgentOrchestrationService:
    """Bridges the /agents endpoints to the agent coordinator."""

    def __init__(self):
        # Reuse the coordinator singleton (mirrors the Week 4/5/6 service pattern).
        self.coordinator = coordinator
        self.settings = get_agent_settings()

    def decide(self, db: Session, payload: dict, *, persist: bool = True) -> dict:
        """
        Run one autonomous decision and return the full OrchestrationResult as a
        dict. `persist` stores the optimization run (False = a throwaway what-if).
        The database session from the HTTP request is passed straight to the
        coordinator so the agents' tool calls use it.
        """
        request = {k: payload[k] for k in _REQUEST_FIELDS if payload.get(k) is not None}
        benchmark = bool(payload.get("benchmark", True))
        result = self.coordinator.run(
            request, db=db, persist=persist, benchmark=benchmark
        )
        return result.as_dict()

    def status(self) -> dict:
        """
        Describe the orchestration layer without touching the database: which
        mode is active, whether CrewAI is installed, the configured LLM, and the
        agents/optimizers available. Powers GET /agents/status.
        """
        return {
            "orchestration_mode": orchestration_mode(self.settings),
            "mode_detail": mode_explanation(self.settings),
            "crewai_installed": crewai_installed(),
            "llm_provider": self.settings.llm_provider,
            "llm_model": self.settings.litellm_model(),
            "agents": [
                "PlannerAgent",
                "ScenarioAgent",
                "OptimizationAgent",
                "EvaluationAgent",
                "ReportingAgent",
            ],
            "optimizers": list(VALID_OPTIMIZERS),
        }


# A ready-to-use singleton, mirroring the Week 4 / 5 / 6 services.
agent_service = AgentOrchestrationService()
