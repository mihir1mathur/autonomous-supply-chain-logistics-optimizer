"""
============================================================================
SCENARIO AGENT  (Week 7)   -- picks which Week 6 scenario to run under
Project: Supply Chain & Logistics Optimizer
============================================================================

THE SCENARIO AGENT'S ONE JOB
----------------------------
  Given the user's request and the Planner's plan, decide the single operating
  SCENARIO the optimization should run under - "what if it is a holiday and
  demand is 1.6x while some vans are down?", "what if a supplier ships late?",
  or simply "normal" for ordinary conditions.

  Crucially, it REUSES the scenarios that already exist in Week 6
  (optimization/scenarios.py, surfaced through the execution service). It does
  NOT define or recreate scenarios - it only CHOOSES one from the existing
  catalog and returns that choice as a structured ScenarioDecision. The scenario
  engine keeps ownership of what each scenario actually does.

HOW IT DECIDES (deterministic reasoning)
----------------------------------------
  * If the request names a scenario and it exists in the catalog, use it.
  * Otherwise infer the best-fit scenario from keywords in the request wording
    (a "holiday" mention -> the holiday scenario, "breakdown" -> vehicle_breakdown).
  * Otherwise default to "normal" (no changes).
  Every chosen key is VALIDATED against the live catalog, so the agent can never
  pick a scenario the platform does not implement. This is the same reasoning
  the CrewAI Scenario agent performs with the scenario-catalog tool.
============================================================================
"""

from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent, AgentValidationError
from agents.tools import ToolContext, get_scenario_catalog
from agents.utils import ScenarioDecision

# Free-text keyword -> scenario key. Checked in order; the first match wins, so
# more specific phrases are listed before the broader ones they contain.
_SCENARIO_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("holiday", ("holiday", "black friday", "christmas", "festive", "seasonal peak")),
    ("demand_spike", ("demand spike", "spike", "surge", "sudden demand")),
    ("high_demand", ("high demand", "busy", "peak demand", "more orders", "heavy demand")),
    ("low_demand", ("low demand", "quiet", "slow period", "off season", "off-season")),
    ("warehouse_closed", ("warehouse closed", "site closed", "closure", "depot shut", "shut down")),
    ("vehicle_failure", ("vehicle failure", "fleet failure", "major failure", "fleet down")),
    ("vehicle_breakdown", ("breakdown", "broke down", "broken down", "van down", "vehicle down", "trucks broke", "half the fleet")),
    ("fuel_price_increase", ("fuel price", "fuel cost", "fuel increase", "diesel", "petrol")),
    ("supplier_delay", ("supplier delay", "supplier late", "stock short", "shortage", "out of stock")),
    ("priority_orders", ("priority orders", "triage", "vip", "most important orders")),
]


class ScenarioAgent(BaseAgent):
    """Chooses one scenario from the existing Week 6 catalog. Chooses only."""

    name = "ScenarioAgent"
    action = "select_scenario"

    def _run(
        self,
        *,
        ctx: ToolContext,
        request: dict[str, Any] | None = None,
        plan: Any | None = None,
    ) -> tuple[ScenarioDecision, str]:
        request = request or {}
        # Reuse the existing scenario engine through the tool (never redefine it).
        catalog = get_scenario_catalog(ctx)
        by_key = {entry["key"]: entry for entry in catalog}

        key, why = self._choose_key(request, by_key)
        entry = by_key[key]

        decision = ScenarioDecision(
            key=key,
            name=entry["name"],
            category=entry["category"],
            description=entry["description"],
            rationale=why,
        )
        summary = f"scenario '{key}' ({entry['name']}) - {why}"
        return decision, summary

    # -----------------------------------------------------------------------
    # VALIDATION  -- the chosen key must exist in the live catalog
    # -----------------------------------------------------------------------
    def _validate(self, result: ScenarioDecision) -> None:
        super()._validate(result)
        if not result.key:
            raise AgentValidationError("Scenario Agent produced an empty scenario key.")

    # -----------------------------------------------------------------------
    # REASONING HELPERS
    # -----------------------------------------------------------------------
    def _choose_key(self, request: dict[str, Any], by_key: dict[str, dict]) -> tuple[str, str]:
        """Return (scenario_key, one-line reason), always a key present in the catalog."""
        # 1) an explicit, valid scenario request wins.
        explicit = request.get("scenario")
        if isinstance(explicit, str) and explicit.lower() in by_key:
            return explicit.lower(), "requested explicitly by the caller"

        # 2) infer from the request wording.
        text = self._request_text(request).lower()
        for key, keywords in _SCENARIO_KEYWORDS:
            if key in by_key and any(word in text for word in keywords):
                return key, f"inferred from the request wording (matched '{key}')"

        # 3) default to the baseline if it exists, else the first catalog entry.
        if "normal" in by_key:
            return "normal", "no special conditions detected - using the baseline"
        first = next(iter(by_key))
        return first, "no baseline in the catalog - using the first available scenario"

    @staticmethod
    def _request_text(request: dict[str, Any]) -> str:
        parts = [
            str(request.get(k, ""))
            for k in ("goal", "request", "query", "scenario", "description", "prompt", "situation")
        ]
        return " ".join(p for p in parts if p)


# A ready-to-use singleton, mirroring the Week 4/5/6 service singletons.
scenario_agent = ScenarioAgent()
