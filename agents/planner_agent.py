"""
============================================================================
PLANNER AGENT  (Week 7)   -- decides WHAT should happen, never HOW
Project: Supply Chain & Logistics Optimizer
============================================================================

THE PLANNER'S ONE JOB
---------------------
  It is the first agent in the crew. It reads the user's optimization request
  and turns it into a structured EXECUTION PLAN: which optimizer to run, on
  which warehouse, at what priority, with what constraints, and why. That is
  all. The Planner NEVER runs an optimization, never touches a solver, and never
  reads the database - it only decides the INTENT. The later agents carry it out.

  Separating "decide what" from "do it" is what keeps the crew clean: if the
  plan is wrong you can see it in one small object before anything expensive
  runs, and the same plan can be executed, re-executed, or simulated later.

HOW IT DECIDES (deterministic reasoning)
----------------------------------------
  A request may state things explicitly (optimizer="fleet") or in plain words
  ("balance the vans across the depot"). The Planner:
    * uses an explicit, valid `optimizer` if given;
    * otherwise INFERS one from keywords in the free-text goal;
    * infers PRIORITY (normal / high) the same way;
    * collects the recognised CONSTRAINTS (max_shipments, ...) to pass along.
  This rule-based reasoning is what runs in the default deterministic mode; in
  CrewAI mode the LLM performs the same reasoning guided by the Planner's
  role/goal/backstory in prompts.py. Either way the OUTPUT is one ExecutionPlan.
============================================================================
"""

from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent, AgentValidationError
from agents.utils import ExecutionPlan

# The four optimizers the platform supports (matches the execution service).
VALID_OPTIMIZERS = ("assignment", "fleet", "routes", "warehouse")

# Free-text keyword -> optimizer, used when the request does not name one. Order
# matters: the first optimizer whose keywords appear wins.
_OPTIMIZER_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("routes", ("route", "routing", "distance", "shortest path", "sequence", "stops")),
    ("warehouse", ("warehouse selection", "which warehouse", "source", "fulfil", "fulfill", "location", "nearest")),
    ("fleet", ("balance", "fleet", "spread", "even load", "utilization", "utilisation")),
    ("assignment", ("assign", "consolidate", "cost", "fewer vehicles", "pack")),
]

# Words that signal an URGENT request (raise the priority to "high").
_HIGH_PRIORITY_WORDS = ("urgent", "priority", "asap", "critical", "immediately", "emergency")

# A short objective label per optimizer (purely descriptive, for the report).
_OBJECTIVE_BY_OPTIMIZER = {
    "assignment": "minimize_cost_and_vehicles",
    "fleet": "balance_vehicle_utilization",
    "routes": "minimize_travel_distance",
    "warehouse": "minimize_fulfilment_distance",
}

# The constraint keys the Planner will forward to the execution service if the
# request supplies them (everything else is ignored).
_CONSTRAINT_KEYS = ("max_shipments", "max_stops", "sample_size", "strategy", "reserve_inventory")


class PlannerAgent(BaseAgent):
    """Builds a structured ExecutionPlan from a user request. Plans only."""

    name = "PlannerAgent"
    action = "build_execution_plan"

    def _run(self, *, request: dict[str, Any] | None = None) -> tuple[ExecutionPlan, str]:
        request = request or {}
        text = self._request_text(request).lower()

        optimizer = self._resolve_optimizer(request, text)
        priority = self._resolve_priority(request, text)
        warehouse_id = request.get("warehouse_id")
        objective = request.get("objective") or _OBJECTIVE_BY_OPTIMIZER.get(optimizer, "optimize")
        constraints = self._collect_constraints(request)

        rationale = self._rationale(optimizer, priority, warehouse_id, request, text)
        steps = [
            f"Run the '{optimizer}' optimizer"
            + (f" on warehouse {warehouse_id}" if warehouse_id else " on an auto-selected warehouse"),
            "Apply the operating scenario chosen by the Scenario Agent",
            "Measure the twelve KPIs and evaluate before-vs-after",
            "Report the outcome with recommendations",
        ]

        plan = ExecutionPlan(
            optimizer=optimizer,
            warehouse_id=warehouse_id,
            priority=priority,
            objective=objective,
            constraints=constraints,
            rationale=rationale,
            steps=steps,
        )
        summary = (
            f"plan: {optimizer} optimizer, priority={priority}, "
            f"warehouse={warehouse_id or 'auto'}, {len(constraints)} constraint(s)"
        )
        return plan, summary

    # -----------------------------------------------------------------------
    # VALIDATION  -- a plan must name a real optimizer and a known priority
    # -----------------------------------------------------------------------
    def _validate(self, result: ExecutionPlan) -> None:
        super()._validate(result)
        if result.optimizer not in VALID_OPTIMIZERS:
            raise AgentValidationError(
                f"Planner chose an invalid optimizer '{result.optimizer}'. "
                f"Allowed: {', '.join(VALID_OPTIMIZERS)}."
            )
        if result.priority not in ("normal", "high"):
            raise AgentValidationError(
                f"Planner chose an invalid priority '{result.priority}'."
            )

    # -----------------------------------------------------------------------
    # REASONING HELPERS
    # -----------------------------------------------------------------------
    @staticmethod
    def _request_text(request: dict[str, Any]) -> str:
        """Gather any free-text fields a caller might use to describe the goal."""
        parts = [
            str(request.get(k, ""))
            for k in ("goal", "request", "query", "objective", "description", "prompt")
        ]
        return " ".join(p for p in parts if p)

    def _resolve_optimizer(self, request: dict[str, Any], text: str) -> str:
        """Use an explicit valid optimizer, else infer one from keywords, else default."""
        explicit = request.get("optimizer")
        if isinstance(explicit, str) and explicit.lower() in VALID_OPTIMIZERS:
            return explicit.lower()
        for optimizer, keywords in _OPTIMIZER_KEYWORDS:
            if any(word in text for word in keywords):
                return optimizer
        # Assignment (consolidate onto fewer, fuller vehicles) is the sensible
        # default when the request does not hint at anything more specific.
        return "assignment"

    def _resolve_priority(self, request: dict[str, Any], text: str) -> str:
        """Use an explicit priority, else raise to 'high' on urgent-sounding text."""
        explicit = request.get("priority")
        if isinstance(explicit, str) and explicit.lower() in ("normal", "high"):
            return explicit.lower()
        if any(word in text for word in _HIGH_PRIORITY_WORDS):
            return "high"
        return "normal"

    @staticmethod
    def _collect_constraints(request: dict[str, Any]) -> dict:
        """Pull out only the recognised constraint keys the caller supplied."""
        return {
            key: request[key]
            for key in _CONSTRAINT_KEYS
            if key in request and request[key] is not None
        }

    @staticmethod
    def _rationale(
        optimizer: str,
        priority: str,
        warehouse_id: str | None,
        request: dict[str, Any],
        text: str,
    ) -> str:
        """One plain-language sentence explaining the plan."""
        why_optimizer = (
            "requested explicitly" if request.get("optimizer") else "inferred from the request wording"
        )
        where = f"warehouse {warehouse_id}" if warehouse_id else "an auto-selected warehouse"
        return (
            f"Chose the '{optimizer}' optimizer ({why_optimizer}) for {where}, "
            f"at {priority} priority. This decides WHAT to run; the Scenario and "
            f"Optimization agents carry it out through the execution service."
        )


# A ready-to-use singleton, mirroring the Week 4/5/6 service singletons.
planner_agent = PlannerAgent()
