"""
============================================================================
REPORT VIEWER
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Displays the Reporting Agent's output the way it was produced - the
  SAME report rendered three ways - using tabs:

        Markdown | Text | JSON

  It also lists the report's recommendations and future improvements, and (when
  present) the optional CrewAI natural-language narrative.

THE DASHBOARD RENDERS THE REPORT - IT DOES NOT WRITE ONE (presentation-layer rule)
----------------------------------------------------------------------
  The report dict comes straight from the API (the reporting agent already
  rendered markdown, text and json). This component only chooses a tab and
  displays the corresponding string/dict. It never composes a report itself.

INPUT
-----
  A `report` dict as returned by the API:
      {"markdown": str, "text": str, "json": dict,
       "recommendations": [str], "future_improvements": [str]}
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.components.kpi_cards import kpi_row
from dashboard.utils.formatting import (
    MISSING,
    business_risks,
    evaluation_indicators,
    evaluation_result,
    format_int,
    format_number,
    humanize_recommendation,
    order_recommendations,
    summarize_improvements,
    title_case,
)

# A realistic, production-oriented engineering roadmap (presentation only - these
# are aspirational next steps, not backend features). Shown as "Future Improvements".
_FUTURE_ROADMAP = [
    "Deploy the backend on AWS (EC2/ECS) with containerized services.",
    "Persist optimization history in a managed PostgreSQL instance.",
    "Add authentication and multi-user, role-based access control.",
    "Provide a real-time KPI monitoring dashboard with live refresh.",
    "Schedule recurring optimization jobs (cron / event-driven triggers).",
    "Extend the engine to multi-objective optimization (cost, service, emissions).",
    "Enable interactive, side-by-side scenario comparison.",
    "Add LLM-powered natural-language explanations of each decision.",
    "Introduce predictive demand forecasting to anticipate spikes.",
    "Adopt advanced OR-Tools vehicle routing (multi-stop VRP).",
]

# One-line business impact statement per evaluation verdict.
_IMPACT_BY_VERDICT = {
    "improved": "The optimized plan outperforms the naive baseline and is recommended for adoption.",
    "degraded": "The optimized plan underperforms the baseline for this scenario - treat it as a risk and prepare contingencies.",
    "mixed": "The plan improves some metrics while regressing others - confirm the priority KPI before committing.",
    "neutral": "The plan performs in line with the baseline for this scenario.",
}


def render_report(
    report: dict,
    *,
    crew_narrative: str | None = None,
    show_recommendations: bool = True,
) -> None:
    """
    Render an agent report with Markdown | Text | JSON tabs, then (optionally)
    its recommendations and any optional AI narrative.

    Set `show_recommendations=False` when the caller renders the recommendations
    separately (e.g. above a collapsed report), so they are not shown twice.
    """
    report = report or {}

    if not any(report.get(k) for k in ("markdown", "text", "json")):
        st.info("No report available. Run an agent decision to generate one.")
        return

    tab_md, tab_text, tab_json = st.tabs(["Markdown", "Text", "JSON"])

    with tab_md:
        markdown = report.get("markdown")
        if markdown:
            st.markdown(markdown)
        else:
            st.info("This report has no markdown rendering.")

    with tab_text:
        text = report.get("text")
        if text:
            # A code block preserves the plain-text report's own layout.
            st.code(text, language="text")
        else:
            st.info("This report has no plain-text rendering.")

    with tab_json:
        payload = report.get("json")
        if payload:
            st.json(payload)
        else:
            st.info("This report has no JSON rendering.")

    if show_recommendations:
        render_recommendations(report)

    # The optional narrative (only present in the LLM mode).
    if crew_narrative:
        st.subheader("Narrative Summary")
        st.markdown(crew_narrative)


def render_recommendations(report: dict) -> None:
    """
    Render the report's recommendations as clean, actionable business bullets.

    Display-only: it lists the recommendations the reporting agent produced,
    stripped of developer-facing API references.
    """
    recommendations = order_recommendations((report or {}).get("recommendations") or [])
    if not recommendations:
        st.caption("No recommendations for this decision.")
        return
    for item in recommendations:
        st.markdown(f"- {humanize_recommendation(item)}")


# ===========================================================================
# EXECUTIVE REPORT SECTIONS  (built from the structured decision data)
# ===========================================================================
def render_execution_badge(optimization: dict) -> None:
    """A clear badge stating whether the report is a stored run or a simulation."""
    optimization = optimization or {}
    if optimization.get("persisted"):
        st.markdown(":green[**🗄 Optimization Run (Stored)**]")
        run_id = optimization.get("run_id")
        if run_id:
            st.caption(f"Run ID: {run_id}")
    else:
        st.markdown(":orange[**🧪 Simulation Report (Not Persisted)**]")


def render_executive_summary(decision: dict) -> None:
    """A concise (~6-8 line) executive summary card built from the decision."""
    scenario = decision.get("scenario") or {}
    plan = decision.get("plan") or {}
    evaluation = decision.get("evaluation") or {}
    improvements = evaluation.get("improvements") or {}
    verdict = str(evaluation.get("verdict") or "").lower()

    result_msg, _ = evaluation_result(verdict)
    scenario_name = scenario.get("name") or scenario.get("key") or MISSING
    category = title_case(scenario.get("category")) if scenario.get("category") else ""
    optimizer = title_case(plan.get("optimizer"))
    objective = title_case(plan.get("objective"))

    bullets = summarize_improvements(improvements)
    improved = [b for b in bullets if "reduced" in b or "improved" in b]
    tradeoffs = [b for b in bullets if "increased" in b or "decreased" in b]

    with st.container(border=True):
        st.markdown(
            f"**Scenario evaluated:** {scenario_name}"
            + (f" ({category})" if category else "")
        )
        st.markdown(f"**Selected optimizer:** {optimizer}  ·  Objective: {objective}")
        st.markdown(f"**Overall verdict:** {result_msg}")
        st.markdown(
            "**Key improvements:** " + (", ".join(improved) if improved else "None material")
        )
        st.markdown(
            "**Primary trade-offs:** " + (", ".join(tradeoffs) if tradeoffs else "None material")
        )
        st.markdown(
            "**Business impact:** "
            + _IMPACT_BY_VERDICT.get(verdict, _IMPACT_BY_VERDICT["neutral"])
        )


def render_kpi_report_cards(kpis: dict) -> None:
    """The 12 report KPIs as unit-labelled KPI cards, laid out in aligned rows."""
    kpis = kpis or {}

    def _pct(frac):
        if isinstance(frac, (int, float)) and not isinstance(frac, bool):
            return f"{frac * 100:.1f}"
        return MISSING

    kpi_row(
        [
            ("Total Cost ($)", format_number(kpis.get("total_cost"), 2),
             "Total plan cost (simulated cost units)."),
            ("Travel Distance (km)", format_number(kpis.get("travel_distance_km"), 1),
             "Total road distance of the plan."),
            ("Vehicle Utilization (%)", _pct(kpis.get("vehicle_utilization")),
             "Share of loaded vehicle capacity used."),
            ("Warehouse Utilization (%)", _pct(kpis.get("warehouse_utilization")),
             "Share of warehouse capacity used."),
        ]
    )
    kpi_row(
        [
            ("Inventory Holding Cost ($)", format_number(kpis.get("inventory_holding_cost"), 2),
             "Cost of holding inventory in the plan."),
            ("Runtime (ms)", format_number(kpis.get("optimization_runtime_ms"), 1),
             "Solver runtime for this run."),
            ("Orders Fulfilled", format_int(kpis.get("orders_fulfilled")),
             "Shipments the plan serves."),
            ("Late Deliveries", format_int(kpis.get("late_deliveries")),
             "Shipments flagged at risk of being late."),
        ]
    )
    kpi_row(
        [
            ("Stockouts", format_int(kpis.get("stockouts")),
             "Demands that could not be met from stock."),
            ("Solver Status", str(kpis.get("solver_status") or MISSING),
             "OR-Tools solver status for this run."),
            ("Model Variables", format_int(kpis.get("num_variables")),
             "Decision variables in the optimization model."),
            ("Model Constraints", format_int(kpis.get("num_constraints")),
             "Constraints in the optimization model."),
        ]
    )


def render_evaluation_report(evaluation: dict) -> None:
    """Evaluation as colour-coded indicators (✓ improved · → neutral · ⚠ watch · ✗ regressed)."""
    rows = evaluation_indicators((evaluation or {}).get("improvements") or {})
    if not rows:
        st.caption("No comparative evaluation is available for this decision.")
        return
    columns = st.columns(2)
    for i, (icon, colour, text) in enumerate(rows):
        columns[i % 2].markdown(f":{colour}[{icon}  {text}]")


def render_business_risks(kpis: dict) -> None:
    """Concise business-oriented risk observations (kept separate from recommendations)."""
    for risk in business_risks(kpis):
        st.markdown(f"- {risk}")


def render_future_roadmap() -> None:
    """The forward-looking engineering roadmap, in two balanced columns."""
    columns = st.columns(2)
    for i, item in enumerate(_FUTURE_ROADMAP):
        columns[i % 2].markdown(f"- {item}")
