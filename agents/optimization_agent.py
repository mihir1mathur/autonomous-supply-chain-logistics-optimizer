"""
============================================================================
OPTIMIZATION AGENT  (Week 7)   -- drives the EXISTING execution service
Project: Supply Chain & Logistics Optimizer
============================================================================

THE OPTIMIZATION AGENT'S ONE JOB
--------------------------------
  Take the Planner's plan and the Scenario Agent's scenario, and actually make
  the platform run the optimization - by calling the EXISTING Week 6 execution
  service through the run-optimization tool. It then returns that result
  unchanged.

  This agent is deliberately THIN. It is the "hands" of the crew, not the brain
  and not the engine:
    * It does NOT call OR-Tools directly.
    * It does NOT duplicate any optimization logic.
    * It does NOT reshape or recompute the numbers.
  All of that already exists and is tested (Week 5 solvers + Week 6 execution
  service). The agent's whole value is orchestration: pass the right arguments,
  press the button, hand the outcome on. Supporting all four optimizers
  (assignment, fleet, routes, warehouse) is simply a matter of forwarding the
  optimizer the Planner chose.

WHY GOING THROUGH THE TOOL MATTERS
----------------------------------
  The tool (agents/tools.py) is the single seam to the platform. Because BOTH
  orchestration modes call the same tool, the actual optimization is always done
  by the trusted execution service - whether a human, the deterministic
  pipeline, or an LLM decided to run it. That is exactly the layered
  architecture the Week 7 goals require:
      agent -> tool -> execution service -> engine -> database.
============================================================================
"""

from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent, AgentError
from agents.tools import ToolContext, run_optimization
from agents.utils import ExecutionPlan, OptimizationOutcome, ScenarioDecision


class OptimizationAgent(BaseAgent):
    """Executes the plan under the scenario by calling the execution service."""

    name = "OptimizationAgent"
    action = "execute_optimization"

    def _run(
        self,
        *,
        ctx: ToolContext,
        plan: ExecutionPlan,
        scenario: ScenarioDecision,
        persist: bool = True,
    ) -> tuple[OptimizationOutcome, str]:
        # Drive the EXISTING execution service via the tool. The tool owns the
        # database session and the full load -> scenario -> solve -> measure ->
        # evaluate -> store pipeline; we only supply the plan's arguments.
        result = run_optimization(
            ctx,
            optimizer=plan.optimizer,
            scenario=scenario.key,
            warehouse_id=plan.warehouse_id,
            persist=persist,
            constraints=plan.constraints,
        )

        outcome = OptimizationOutcome(
            optimizer=plan.optimizer,
            scenario=scenario.key,
            invoked="execution_service.run" if persist else "execution_service.simulate",
            persisted=bool(result.get("persisted")),
            run_id=result.get("run_id"),
            success=bool(result.get("success")),
            result=result,
        )
        status = result.get("solver_status", "UNKNOWN")
        run_id = result.get("run_id") or "(not stored)"
        summary = (
            f"ran {plan.optimizer}/{scenario.key} via "
            f"{'run' if persist else 'simulate'} -> success={outcome.success}, "
            f"status={status}, run_id={run_id}"
        )
        return outcome, summary

    # -----------------------------------------------------------------------
    # VALIDATION  -- we must have a real result dict with metrics
    # -----------------------------------------------------------------------
    def _validate(self, result: OptimizationOutcome) -> None:
        super()._validate(result)
        if not isinstance(result.result, dict) or "metrics" not in result.result:
            raise AgentError(
                "Optimization Agent did not receive a valid result (no metrics) "
                "from the execution service."
            )


# A ready-to-use singleton, mirroring the Week 4/5/6 service singletons.
optimization_agent = OptimizationAgent()
