"""
============================================================================
REPORTING AGENT  (Week 7)   -- turns the whole decision into a readable report
Project: Supply Chain & Logistics Optimizer
============================================================================

THE REPORTING AGENT'S ONE JOB
-----------------------------
  It is the last agent in the crew. It takes everything the others decided and
  measured - the plan, the scenario, the KPIs, the evaluation verdict - and
  writes the FINAL REPORT of the decision. The same report is rendered three
  ways so it can serve three audiences:

      * markdown  - for a human to read (headings, a KPI table, sections).
      * text      - a plain-text version for logs and terminals.
      * json      - a structured object for a program or a dashboard to ingest.

  It also produces two action lists the goals ask for: RECOMMENDATIONS (what to
  do now, given the results) and FUTURE IMPROVEMENTS (how the platform could go
  further). Both are derived from the actual outcome, not boilerplate.

WHY A DEDICATED REPORTING STEP
------------------------------
  The other agents deal in structured data; humans and dashboards need
  something readable. Separating "produce the numbers" from "communicate them"
  keeps each job simple and means the report format can change without touching
  any decision logic. The three renderings share ONE underlying JSON structure,
  so they can never drift apart, and the markdown/json split is exactly what a
  future dashboard (Week 8) will consume.
============================================================================
"""

from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from agents.utils import (
    AgentReport,
    EvaluationSummary,
    ExecutionPlan,
    OptimizationOutcome,
    ScenarioDecision,
    to_jsonable,
)

# The KPIs we surface in the report, in the order the Week 7 goals list them,
# paired with a human label and a unit/suffix.
_KPI_ROWS = [
    ("total_cost", "Total cost", ""),
    ("travel_distance_km", "Travel distance", " km"),
    ("vehicle_utilization", "Vehicle utilization", ""),
    ("warehouse_utilization", "Warehouse utilization", ""),
    ("inventory_holding_cost", "Inventory holding cost", ""),
    ("stockouts", "Stockouts", ""),
    ("late_deliveries", "Late deliveries", ""),
    ("orders_fulfilled", "Orders fulfilled", ""),
    ("optimization_runtime_ms", "Runtime", " ms"),
    ("solver_status", "Solver status", ""),
    ("num_variables", "Model variables", ""),
    ("num_constraints", "Model constraints", ""),
]


class ReportingAgent(BaseAgent):
    """Renders the whole decision as markdown, text and JSON, with actions."""

    name = "ReportingAgent"
    action = "write_report"

    def _run(
        self,
        *,
        request: dict[str, Any],
        plan: ExecutionPlan,
        scenario: ScenarioDecision,
        evaluation: EvaluationSummary,
        outcome: OptimizationOutcome,
        mode: str = "deterministic",
        mode_detail: str = "",
    ) -> tuple[AgentReport, str]:
        kpis = evaluation.kpis or {}
        recommendations = self._recommendations(evaluation, outcome, plan)
        future = self._future_improvements(mode)

        # ONE underlying JSON structure; markdown/text render from the same data.
        json_report = {
            "title": "Autonomous Supply Chain Decision Report",
            "orchestration_mode": mode,
            "orchestration_mode_detail": mode_detail,
            "request": to_jsonable(request),
            "plan": plan.as_dict(),
            "scenario": scenario.as_dict(),
            "run": {
                "run_id": outcome.run_id,
                "persisted": outcome.persisted,
                "invoked": outcome.invoked,
                "success": outcome.success,
            },
            "verdict": evaluation.verdict,
            "headline": evaluation.headline,
            "kpis": to_jsonable(kpis),
            "improvements": to_jsonable(evaluation.improvements),
            "benchmark": to_jsonable(evaluation.benchmark),
            "notes": list(evaluation.notes),
            "recommendations": recommendations,
            "future_improvements": future,
        }

        markdown = self._render_markdown(json_report)
        text = self._render_text(json_report)

        report = AgentReport(
            markdown=markdown,
            text=text,
            json=json_report,
            recommendations=recommendations,
            future_improvements=future,
        )
        summary = f"report written ({len(markdown)} chars, {len(recommendations)} recommendation(s))"
        return report, summary

    # -----------------------------------------------------------------------
    # ACTION LISTS  -- derived from the real outcome, not boilerplate
    # -----------------------------------------------------------------------
    @staticmethod
    def _recommendations(
        evaluation: EvaluationSummary,
        outcome: OptimizationOutcome,
        plan: ExecutionPlan,
    ) -> list[str]:
        recs: list[str] = []
        kpis = evaluation.kpis or {}
        verdict = evaluation.verdict

        if verdict == "improved":
            recs.append(
                f"Adopt the '{plan.optimizer}' plan under the '{outcome.scenario}' "
                f"scenario: it beats the un-optimized baseline on the key metrics."
            )
        elif verdict == "degraded":
            recs.append(
                f"Treat the '{outcome.scenario}' scenario as a risk: this plan does "
                f"worse than the baseline, so prepare contingencies before it occurs."
            )
        elif verdict == "mixed":
            recs.append(
                "Trade-offs present: the plan wins on some metrics and loses on "
                "others - confirm which KPI matters most before committing."
            )
        else:
            recs.append("No material change vs the baseline under this scenario.")

        if int(kpis.get("stockouts", 0) or 0) > 0:
            recs.append(
                "Stockouts occurred: add fleet capacity, pre-position inventory, or "
                "run the 'warehouse' optimizer to spread demand across more sites."
            )
        if int(kpis.get("late_deliveries", 0) or 0) > 0:
            recs.append(
                "Deliveries are at risk of lateness: run the 'fleet' optimizer to "
                "rebalance load off the over-full vehicles."
            )
        if outcome.persisted and outcome.run_id:
            recs.append(
                f"Run {outcome.run_id} is stored in the history; compare it against "
                f"past runs via GET /optimization/metrics."
            )
        return recs

    @staticmethod
    def _future_improvements(mode: str) -> list[str]:
        items = [
            "Feed the stored optimization_runs into a monitoring dashboard "
            "(planned Week 8) to chart KPIs and evaluations over time.",
            "Implement the reserved OR-Tools VRP routing strategy so the 'routes' "
            "optimizer can plan multiple vehicles, not just order one vehicle's stops.",
            "Let the crew trial several optimizers/scenarios and recommend the best, "
            "turning single decisions into autonomous what-if exploration.",
        ]
        if mode != "crewai":
            items.insert(
                0,
                "Enable the CrewAI LLM mode (install crewai and set the provider API "
                "key) for natural-language planning and richer explanations.",
            )
        return items

    # -----------------------------------------------------------------------
    # RENDERERS  -- markdown and plain text from the ONE json structure
    # -----------------------------------------------------------------------
    @staticmethod
    def _fmt(value: Any) -> str:
        """Format a KPI value tidily (floats to 2 dp, ints as-is, else str)."""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def _render_markdown(self, r: dict) -> str:
        kpis = r["kpis"]
        lines: list[str] = []
        lines.append(f"# {r['title']}")
        lines.append("")
        lines.append(f"**Verdict:** {r['verdict'].upper()} - {r['headline']}")
        lines.append("")
        lines.append(f"- **Orchestration mode:** {r['orchestration_mode']} ({r['orchestration_mode_detail']})")
        lines.append(f"- **Scenario:** {r['scenario']['name']} (`{r['scenario']['key']}`) - {r['scenario']['description']}")
        lines.append(f"- **Optimizer:** `{r['plan']['optimizer']}` (priority: {r['plan']['priority']})")
        run = r["run"]
        lines.append(
            f"- **Run:** {'stored as ' + run['run_id'] if run['persisted'] else 'simulated (not stored)'}"
            f" - success: {run['success']}"
        )
        lines.append("")

        # KPI table.
        lines.append("## Key Performance Indicators")
        lines.append("")
        lines.append("| KPI | Value |")
        lines.append("| --- | --- |")
        for key, label, suffix in _KPI_ROWS:
            if key in kpis:
                lines.append(f"| {label} | {self._fmt(kpis[key])}{suffix} |")
        lines.append("")

        # Evaluation.
        if r["improvements"]:
            lines.append("## Evaluation (before vs after, positive = better)")
            lines.append("")
            for key, val in r["improvements"].items():
                nice = key.replace("_percent", "").replace("_", " ")
                lines.append(f"- {nice}: {self._fmt(val)}%")
            lines.append("")

        # Benchmark.
        if r["benchmark"]:
            b = r["benchmark"]
            lines.append(f"## Benchmark vs `{b['reference_scenario']}`")
            lines.append("")
            lines.append(f"- Cost delta: {self._fmt(b['cost_delta'])}")
            lines.append(f"- Distance delta: {self._fmt(b['distance_delta_km'])} km")
            lines.append(f"- Stockouts delta: {b['stockouts_delta']}")
            lines.append(f"- Late deliveries delta: {b['late_deliveries_delta']}")
            lines.append("")

        # Notes.
        if r["notes"]:
            lines.append("## Notes")
            lines.append("")
            for note in r["notes"]:
                lines.append(f"- {note}")
            lines.append("")

        # Recommendations.
        lines.append("## Recommendations")
        lines.append("")
        for rec in r["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

        # Future improvements.
        lines.append("## Future Improvements")
        lines.append("")
        for item in r["future_improvements"]:
            lines.append(f"- {item}")
        lines.append("")

        return "\n".join(lines)

    def _render_text(self, r: dict) -> str:
        """A plain-text rendering (no markdown syntax) for logs/terminals."""
        kpis = r["kpis"]
        lines: list[str] = []
        lines.append(r["title"].upper())
        lines.append("=" * len(r["title"]))
        lines.append(f"Verdict: {r['verdict'].upper()} - {r['headline']}")
        lines.append(f"Mode: {r['orchestration_mode']} ({r['orchestration_mode_detail']})")
        lines.append(f"Scenario: {r['scenario']['name']} [{r['scenario']['key']}]")
        lines.append(f"Optimizer: {r['plan']['optimizer']} (priority {r['plan']['priority']})")
        run = r["run"]
        lines.append(
            "Run: " + (f"stored {run['run_id']}" if run["persisted"] else "simulated")
            + f" (success={run['success']})"
        )
        lines.append("")
        lines.append("KPIs:")
        for key, label, suffix in _KPI_ROWS:
            if key in kpis:
                lines.append(f"  - {label}: {self._fmt(kpis[key])}{suffix}")
        if r["notes"]:
            lines.append("")
            lines.append("Notes:")
            for note in r["notes"]:
                lines.append(f"  - {note}")
        lines.append("")
        lines.append("Recommendations:")
        for rec in r["recommendations"]:
            lines.append(f"  - {rec}")
        return "\n".join(lines)


# A ready-to-use singleton, mirroring the Week 4/5/6 service singletons.
reporting_agent = ReportingAgent()
