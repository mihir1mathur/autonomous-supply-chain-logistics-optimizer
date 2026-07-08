"""
============================================================================
EVALUATION AGENT  (Week 7)   -- judges the outcome, reusing Week 6 numbers
Project: Supply Chain & Logistics Optimizer
============================================================================

THE EVALUATION AGENT'S ONE JOB
------------------------------
  Read the result the Optimization Agent produced and turn it into a clear
  judgement a human can act on: what did the run cost and save, did it improve
  operations, and is there anything to worry about?

  It REUSES the Week 6 numbers verbatim - the twelve KPIs from metrics.py and
  the before-vs-after percentages from evaluation.py, both already computed by
  the execution service. This agent does NOT recompute any metric; it INTERPRETS
  the existing ones: it derives an overall VERDICT (improved / degraded / mixed /
  neutral), writes a one-line headline, and raises notes for anything a manager
  should notice (stockouts, at-risk deliveries).

  Optionally it adds a BENCHMARK COMPARISON: when the run was under a stressed
  scenario, it re-runs the same optimizer under "normal" (a throwaway simulate,
  through the same tool) so the report can say how much the scenario cost
  relative to ordinary operations. That comparison, too, is produced by the
  execution service - the agent only asks for it and reads the answer.
============================================================================
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from agents.tools import ToolContext, run_optimization
from agents.utils import EvaluationSummary, OptimizationOutcome

# The six improvement percentages we weigh when forming a verdict. Each is
# signed so that POSITIVE always means "better" (see optimization/evaluation.py).
_IMPROVEMENT_FIELDS = (
    "cost_reduction_percent",
    "distance_reduction_percent",
    "stockout_reduction_percent",
    "late_delivery_reduction_percent",
    "utilization_improvement_percent",
    "delivery_improvement_percent",
)

# A change smaller than this (in percentage points) counts as "no real change",
# so tiny rounding wobble does not read as an improvement or a regression.
_NOISE_THRESHOLD = 0.5


class EvaluationAgent(BaseAgent):
    """Interprets a run's KPIs and evaluation into a verdict + benchmark."""

    name = "EvaluationAgent"
    action = "evaluate_outcome"

    def _run(
        self,
        *,
        ctx: ToolContext,
        outcome: OptimizationOutcome,
        benchmark: bool = True,
    ) -> tuple[EvaluationSummary, str]:
        result = outcome.result or {}
        kpis: dict = result.get("metrics") or {}
        evaluation: dict = result.get("evaluation") or {}

        verdict = self._verdict(evaluation)
        headline = self._headline(verdict, evaluation, kpis)
        notes = self._notes(kpis)
        comparison = self._benchmark(ctx, outcome) if benchmark else None

        summary_obj = EvaluationSummary(
            verdict=verdict,
            headline=headline,
            kpis=kpis,
            improvements=self._improvement_slice(evaluation),
            benchmark=comparison,
            notes=notes,
        )
        summary = f"verdict={verdict}; {headline}"
        return summary_obj, summary

    # -----------------------------------------------------------------------
    # VERDICT + HEADLINE
    # -----------------------------------------------------------------------
    def _verdict(self, evaluation: dict) -> str:
        """Turn the signed improvement percentages into one overall verdict."""
        if not evaluation:
            return "neutral"
        gains = [float(evaluation.get(f, 0.0) or 0.0) for f in _IMPROVEMENT_FIELDS]
        better = sum(1 for g in gains if g > _NOISE_THRESHOLD)
        worse = sum(1 for g in gains if g < -_NOISE_THRESHOLD)
        if better and not worse:
            return "improved"
        if worse and not better:
            return "degraded"
        if not better and not worse:
            return "neutral"
        return "mixed"

    @staticmethod
    def _headline(verdict: str, evaluation: dict, kpis: dict) -> str:
        """A one-line, human-first summary; prefer the framework's own summary."""
        if evaluation.get("summary"):
            return f"{verdict.capitalize()} - {evaluation['summary']}"
        # Fall back to the raw KPIs when there is no evaluation (rare).
        return (
            f"{verdict.capitalize()} - cost {kpis.get('total_cost', 0)}, "
            f"distance {kpis.get('travel_distance_km', 0)} km, "
            f"{kpis.get('orders_fulfilled', 0)} orders, "
            f"{kpis.get('stockouts', 0)} stockouts."
        )

    @staticmethod
    def _improvement_slice(evaluation: dict) -> dict:
        """The named improvement percentages the Week 7 goals list, if present."""
        if not evaluation:
            return {}
        keys = _IMPROVEMENT_FIELDS + ("inventory_reduction_percent", "resource_utilization_percent")
        return {k: evaluation[k] for k in keys if k in evaluation}

    # -----------------------------------------------------------------------
    # NOTES  -- things a human should notice
    # -----------------------------------------------------------------------
    @staticmethod
    def _notes(kpis: dict) -> list[str]:
        notes: list[str] = []
        stockouts = int(kpis.get("stockouts", 0) or 0)
        late = int(kpis.get("late_deliveries", 0) or 0)
        if stockouts > 0:
            notes.append(
                f"{stockouts} order(s) could not be served under this scenario "
                f"(stockouts) - capacity or stock is the binding constraint."
            )
        if late > 0:
            notes.append(
                f"{late} delivery(ies) are flagged at risk of being late (a "
                f"utilization proxy) - the fleet is running hot."
            )
        if not notes:
            notes.append("No stockouts and no at-risk deliveries under this scenario.")
        return notes

    # -----------------------------------------------------------------------
    # BENCHMARK COMPARISON  -- this run vs the same optimizer under "normal"
    # -----------------------------------------------------------------------
    def _benchmark(self, ctx: ToolContext, outcome: OptimizationOutcome) -> dict | None:
        """
        Compare a stressed run to ordinary operations by simulating the SAME
        optimizer under "normal" (a throwaway, non-persisted run through the tool)
        and reporting the KPI deltas. Skipped when the run itself was already
        "normal" (nothing to compare against) or when it did not succeed.
        """
        if outcome.scenario == "normal" or not outcome.success:
            return None
        try:
            reference = run_optimization(
                ctx,
                optimizer=outcome.optimizer,
                scenario="normal",
                warehouse_id=(outcome.result or {}).get("warehouse_id"),
                persist=False,
                constraints=None,
            )
        except Exception as exc:  # noqa: BLE001 - a benchmark is best-effort only.
            self.logger.warning("benchmark comparison skipped: %s", exc)
            return None
        finally:
            # run_optimization stashed the reference on the blackboard; restore
            # the ORIGINAL outcome so later readers still see the real run.
            ctx.last_outcome = outcome.result

        this_kpis = (outcome.result or {}).get("metrics") or {}
        ref_kpis = reference.get("metrics") or {}
        return {
            "reference_scenario": "normal",
            "this_scenario": outcome.scenario,
            "cost_delta": round(this_kpis.get("total_cost", 0) - ref_kpis.get("total_cost", 0), 2),
            "distance_delta_km": round(
                this_kpis.get("travel_distance_km", 0) - ref_kpis.get("travel_distance_km", 0), 2
            ),
            "stockouts_delta": int(this_kpis.get("stockouts", 0)) - int(ref_kpis.get("stockouts", 0)),
            "late_deliveries_delta": int(this_kpis.get("late_deliveries", 0))
            - int(ref_kpis.get("late_deliveries", 0)),
            "this_kpis": this_kpis,
            "reference_kpis": ref_kpis,
        }


# A ready-to-use singleton, mirroring the Week 4/5/6 service singletons.
evaluation_agent = EvaluationAgent()
