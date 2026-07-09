"""
============================================================================
AGENT DECISIONS PAGE
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE DOES
-------------------
  Lets a user type a plain-English request - e.g. "Optimize deliveries for a
  holiday rush and reduce late deliveries." - and hands it to the agent crew:

    * "Decide"   -> POST /agents/decide   (runs the crew and STORES the run)
    * "Simulate" -> POST /agents/simulate (a what-if; the run is NOT stored)

  Then it shows everything the crew produced:
    * a success/message banner,
    * the execution plan and the scenario chosen,
    * the optimization outcome (stored run id or a what-if),
    * a business-friendly evaluation summary + KPIs + baseline comparison,
    * the five-agent execution trace (auditable),
    * the actionable recommendations, and
    * a collapsible report (Markdown | Text | JSON) - with export buttons.

  The last decision is remembered in st.session_state so the Reports page can
  show the same report without re-running the crew.

DASHBOARD DECIDES NOTHING ITSELF
  The reasoning, the optimization and the report are ALL produced by the
  backend agents. This page only collects the request and renders the response.
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.agent_trace import render_agent_trace
from dashboard.components.charts import improvement_bar
from dashboard.components.filters import OPTIMIZERS
from dashboard.components.kpi_cards import run_kpi_cards
from dashboard.components.report_viewer import render_recommendations, render_report
from dashboard.utils.export import download_report_json, download_report_markdown
from dashboard.utils.formatting import (
    evaluation_result,
    format_currency,
    format_distance_km,
    format_int,
    humanize_decision_message,
    summarize_improvements,
    title_case,
)

# The session-state key the Reports page also reads.
LAST_DECISION_KEY = "last_agent_decision"

EXAMPLE_GOAL = "Optimize deliveries for a holiday rush and reduce late deliveries."


def render(client: APIClient) -> None:
    """Render the Agent Decisions page."""
    st.header("Agent Decisions")
    st.caption(
        "Describe what you want in plain English. The five-agent crew (Planner, "
        "Scenario, Optimization, Evaluation, Reporting) plans, runs, judges and "
        "explains the optimization - by orchestrating the existing backend."
    )

    # ---- The request form ------------------------------------------------
    goal, overrides, action = _render_request_form(client)

    if action:
        _run_decision(client, goal, overrides, persist=(action == "decide"))

    # ---- Show the last decision (this run, or a previous one) -------------
    decision = st.session_state.get(LAST_DECISION_KEY)
    if decision:
        _render_decision(decision)
    else:
        st.info("Submit a request above to see the crew's decision, trace and report.")


def _render_request_form(client: APIClient):
    """Render the goal + optional overrides form. Returns (goal, overrides, action)."""
    scenario_keys = _scenario_keys(client)
    any_label = "(let the agent decide)"

    with st.form("agent_decision_form"):
        goal = st.text_area(
            "Your request (plain English)",
            value=EXAMPLE_GOAL,
            height=90,
            help="The Planner and Scenario agents infer the optimizer and scenario "
            "from this text. You can also pin them with the overrides below.",
        )

        with st.expander("Optional overrides", expanded=False):
            cols = st.columns(3)
            with cols[0]:
                optimizer = st.selectbox("Preferred Optimizer", [any_label] + OPTIMIZERS, index=0)
            with cols[1]:
                scenario = st.selectbox("Scenario Override", [any_label] + scenario_keys, index=0)
            with cols[2]:
                priority = st.selectbox("Priority", [any_label, "normal", "high"], index=0)
            cols2 = st.columns(3)
            with cols2[0]:
                warehouse_id = st.text_input(
                    "Warehouse (optional)", value="", placeholder="Auto-select warehouse"
                )
            with cols2[1]:
                max_shipments = st.number_input("Max Shipments", min_value=1, value=40, step=5)
            with cols2[2]:
                benchmark = st.checkbox("Compare with Normal Operations", value=True)

        btn_cols = st.columns(2)
        decide = btn_cols[0].form_submit_button("Run & Save Optimization", type="primary")
        simulate = btn_cols[1].form_submit_button("Run What-If Simulation")

    overrides = {
        "optimizer": None if optimizer == any_label else optimizer,
        "scenario": None if scenario == any_label else scenario,
        "priority": None if priority == any_label else priority,
        "warehouse_id": warehouse_id.strip() or None,
        "max_shipments": int(max_shipments),
        "benchmark": bool(benchmark),
    }
    action = "decide" if decide else ("simulate" if simulate else None)
    return goal, overrides, action


def _run_decision(client: APIClient, goal: str, overrides: dict, *, persist: bool) -> None:
    """Call /agents/decide or /agents/simulate and store the result in session."""
    payload = {"goal": goal.strip() or None}
    # Only include overrides that were actually set (None values are dropped).
    for key, value in overrides.items():
        if value is not None:
            payload[key] = value

    verb = "decide" if persist else "simulate"
    try:
        with st.spinner(f"Running the crew ({verb})... this runs a real optimization."):
            decision = client.agent_decide(payload) if persist else client.agent_simulate(payload)
    except APIError as exc:
        st.error(f"The agent request failed. {exc.message}")
        return

    st.session_state[LAST_DECISION_KEY] = decision


def _render_decision(decision: dict) -> None:
    """Render a full OrchestrationResult: plan, scenario, outcome, eval, trace, report."""
    # ---- Headline banner (success + message) -----------------------------
    success = decision.get("success")
    message = humanize_decision_message(decision.get("message", ""))

    st.subheader("Decision")
    if success:
        st.success(message or "The crew completed the decision successfully.")
    else:
        st.error(message or "The crew stopped before completing. See the trace below.")

    # ---- Plan + Scenario (clean, labelled - no raw dicts) ----------------
    plan = decision.get("plan", {})
    scenario = decision.get("scenario", {})
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Execution Plan**")
        st.markdown(
            f"- **Optimizer:** {title_case(plan.get('optimizer'))}\n"
            f"- **Warehouse:** {plan.get('warehouse_id') or 'Auto-select'}\n"
            f"- **Priority:** {title_case(plan.get('priority'))}\n"
            f"- **Objective:** {title_case(plan.get('objective'))}"
        )
        if plan.get("rationale"):
            st.caption(plan["rationale"])
    with cols[1]:
        st.markdown("**Scenario**")
        st.markdown(
            f"- **Name:** {scenario.get('name') or '-'}\n"
            f"- **Category:** {title_case(scenario.get('category'))}"
        )
        if scenario.get("rationale"):
            st.caption(scenario["rationale"])

    st.divider()

    # ---- Optimization outcome (business wording, no dev internals) --------
    opt = decision.get("optimization", {})
    st.markdown("**Optimization Outcome**")
    exec_mode = "What-If Simulation" if "simulate" in str(opt.get("invoked", "")) else "Optimization Run"
    outcome_cols = st.columns(3)
    outcome_cols[0].metric("Execution Mode", exec_mode)
    outcome_cols[1].metric("Stored", "Yes" if opt.get("persisted") else "No (what-if)")
    outcome_cols[2].metric("Run ID", opt.get("run_id") or "-")
    if opt.get("run_id"):
        st.caption("Run ID (click the copy icon to copy):")
        st.code(opt["run_id"], language="text")

    # ---- Evaluation (summary + KPIs + comparisons) -----------------------
    evaluation = decision.get("evaluation", {})
    if evaluation:
        st.divider()
        _render_evaluation(evaluation)

    # ---- Execution trace (auditable five-agent flow) ---------------------
    st.divider()
    st.subheader("Execution Trace")
    render_agent_trace(decision.get("trace", {}), scenario_name=scenario.get("name"))

    # ---- Recommendations (kept visible - actionable business insights) ---
    report = decision.get("report", {})
    st.divider()
    st.subheader("Recommendations")
    render_recommendations(report)

    # ---- Report, collapsed by default, with exports ----------------------
    with st.expander("Decision Report", expanded=False):
        render_report(
            report,
            crew_narrative=decision.get("crew_narrative"),
            show_recommendations=False,
        )
        if report:
            exp_cols = st.columns(2)
            with exp_cols[0]:
                download_report_markdown(report, key="agent_report_md")
            with exp_cols[1]:
                download_report_json(report, key="agent_report_json")


def _render_evaluation(evaluation: dict) -> None:
    """Render the business-friendly evaluation: overall result, KPIs, comparisons."""
    st.subheader("Evaluation Summary")

    # Overall result - a plain verdict with a tone-matched banner.
    result_msg, tone = evaluation_result(evaluation.get("verdict"))
    st.markdown("**Overall Result**")
    if tone == "good":
        st.success(result_msg)
    elif tone == "bad":
        st.error(result_msg)
    else:
        st.info(result_msg)

    # Concise change bullets (derived from the already-computed improvements).
    for bullet in summarize_improvements(evaluation.get("improvements")):
        st.markdown(f"- {bullet}")

    # The optimized run's KPIs (shown once, here).
    kpis = evaluation.get("kpis") or {}
    if kpis:
        st.markdown("**Key Performance Indicators**")
        run_kpi_cards(kpis)

    # Visual comparison against the naive baseline (the chart renders its own
    # "Comparison with Baseline" title, so no separate heading is needed here).
    improvements = evaluation.get("improvements") or {}
    if improvements:
        improvement_bar(improvements, title="Comparison with Baseline")
        st.caption("Positive values indicate improvement; negative values indicate regression.")

    _render_benchmark(evaluation.get("benchmark"))


def _render_benchmark(benchmark: dict | None) -> None:
    """Show the optional 'vs normal' comparison in human-readable wording."""
    if not benchmark:
        return
    st.markdown("**Comparison with Normal Operations**")
    cols = st.columns(3)
    cols[0].metric(
        "Cost",
        _delta_phrase(benchmark.get("cost_delta"), "cheaper", "more expensive",
                      lambda v: format_currency(v, 0)),
    )
    cols[1].metric(
        "Distance",
        _delta_phrase(benchmark.get("distance_delta_km"), "shorter", "longer",
                      lambda v: format_distance_km(v, 0)),
    )
    cols[2].metric(
        "Stockouts",
        _delta_phrase(benchmark.get("stockouts_delta"), "fewer", "more", format_int),
    )


def _delta_phrase(delta, better_word: str, worse_word: str, formatter) -> str:
    """
    Turn a benchmark delta (this - normal, where NEGATIVE is better) into a
    human-readable phrase like '↓ $8,700 cheaper' or '↑ 12 more'.
    """
    if not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return "-"
    if abs(delta) < 0.05:
        return "No change"
    magnitude = formatter(abs(delta))
    if delta < 0:
        return f"↓ {magnitude} {better_word}"
    return f"↑ {magnitude} {worse_word}"


def _scenario_keys(client: APIClient) -> list[str]:
    """Scenario keys for the override box (empty if the catalog is unavailable)."""
    try:
        catalog = client.get_scenarios()
        return [s.get("key") for s in catalog.get("scenarios", []) if s.get("key")]
    except APIError:
        return []
