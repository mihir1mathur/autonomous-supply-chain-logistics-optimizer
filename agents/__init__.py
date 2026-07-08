"""
============================================================================
agents/ package  (Week 7)   -- the AI MULTI-AGENT ORCHESTRATION LAYER
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT LIVES HERE
---------------
  The Week 7 layer that turns the platform into an AUTONOMOUS SUPPLY CHAIN
  DECISION SYSTEM. Five specialised agents cooperate - orchestrated by a
  coordinator - to take a plain user request and produce a complete, recorded
  decision, entirely by driving the EXISTING Week 6 execution service (never
  OR-Tools directly):

      base_agent.py        the shared shell every agent inherits (logging,
                           timing, error handling, validation, tracing).
      planner_agent.py     decides WHAT to run (ExecutionPlan). Plans only.
      scenario_agent.py    chooses one EXISTING Week 6 scenario (ScenarioDecision).
      optimization_agent.py drives the execution service (OptimizationOutcome).
      evaluation_agent.py  judges the KPIs + evaluation (EvaluationSummary).
      reporting_agent.py   writes the report (AgentReport: markdown/json/text).
      coordinator.py       the orchestrator that runs all five in order.
      crew.py              the real CrewAI assembly (optional LLM mode).
      tools.py             the ONLY seam to the platform (execution-service tools).
      prompts.py           each agent's role/goal/backstory + task templates.
      config.py            settings + which orchestration mode to use.
      utils.py             logging/timing/tracing + the structured contracts.

HOW IT FITS THE ARCHITECTURE (Week 7 goals)
-------------------------------------------
      User -> FastAPI (/agents) -> Execution Service (agent_service)
           -> Coordinator -> Planner -> Scenario -> Optimization -> Evaluation
           -> Reporting -> Execution Service -> Optimization Engine -> Database

  Everything is ADDITIVE: no Week 0-6 file is rewritten. The agents REUSE the
  Week 6 execution service, scenario engine, metrics and evaluation framework.

TWO ORCHESTRATION MODES
-----------------------
  * deterministic (default, always available, offline, reproducible).
  * crewai (optional: crewai installed + an LLM key) - adds natural-language
    reasoning/narration on top of the same deterministic numbers.

QUICK START
-----------
      from agents import coordinator
      result = coordinator.run({"goal": "optimize deliveries for a holiday peak"})
      print(result.report["markdown"])
============================================================================
"""

from agents.config import AgentSettings, get_agent_settings, orchestration_mode
from agents.coordinator import AgentCoordinator, coordinator
from agents.utils import (
    AgentReport,
    EvaluationSummary,
    ExecutionPlan,
    OptimizationOutcome,
    OrchestrationResult,
    ScenarioDecision,
)

__all__ = [
    "AgentCoordinator",
    "coordinator",
    "AgentSettings",
    "get_agent_settings",
    "orchestration_mode",
    "ExecutionPlan",
    "ScenarioDecision",
    "OptimizationOutcome",
    "EvaluationSummary",
    "AgentReport",
    "OrchestrationResult",
]
