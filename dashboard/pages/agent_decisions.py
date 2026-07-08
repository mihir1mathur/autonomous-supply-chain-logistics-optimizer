"""
============================================================================
AGENT DECISIONS PAGE  (Week 8, Part 9)  -- the key Week 8 page
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE DOES
-------------------
  Lets a user type a plain-English request - e.g. "Optimize deliveries for a
  holiday rush and reduce late deliveries." - and hands it to the Week 7 crew:

    * "Decide"   -> POST /agents/decide   (runs the crew and STORES the run)
    * "Simulate" -> POST /agents/simulate (a what-if; the run is NOT stored)

  Then it shows everything the crew produced:
    * the mode (deterministic / crewai) and a success/message banner,
    * the Planner's plan and the Scenario chosen,
    * the optimization outcome (stored run_id or 'simulated'),
    * the Evaluation verdict + KPIs + improvement chart,
    * the five-agent execution trace (auditable), and
    * the report (Markdown | Text | JSON) with recommendations, plus any
      optional CrewAI narrative - with export buttons.

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
from dashboard.components.report_viewer import render_report
from dashboard.utils.export import download_report_json, download_report_markdown

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
                optimizer = st.selectbox("Force optimizer", [any_label] + OPTIMIZERS, index=0)
            with cols[1]:
                scenario = st.selectbox("Force scenario", [any_label] + scenario_keys, index=0)
            with cols[2]:
                priority = st.selectbox("Priority", [any_label, "normal", "high"], index=0)
            cols2 = st.columns(3)
            with cols2[0]:
                warehouse_id = st.text_input("Warehouse id", value="", placeholder="auto if blank")
            with cols2[1]:
                max_shipments = st.number_input("Max shipments", min_value=1, value=40, step=5)
            with cols2[2]:
                benchmark = st.checkbox("Benchmark vs. normal", value=True)

        btn_cols = st.columns(2)
        decide = btn_cols[0].form_submit_button("Decide (store the run)", type="primary")
        simulate = btn_cols[1].form_submit_button("Simulate (what-if, not stored)")

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
    # ---- Headline banner (mode + success + message) ----------------------
    mode = decision.get("mode", "deterministic")
    mode_detail = decision.get("mode_detail", "")
    success = decision.get("success")
    message = decision.get("message", "")

    st.subheader("Decision")
    st.caption(f"Mode: **{mode}**  -  {mode_detail}")
    if success:
        st.success(message or "The crew completed the decision successfully.")
    else:
        st.error(message or "The crew stopped before completing. See the trace below.")

    # ---- Plan + Scenario -------------------------------------------------
    plan = decision.get("plan", {})
    scenario = decision.get("scenario", {})
    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Planner output**")
        st.write(
            {
                "optimizer": plan.get("optimizer"),
                "warehouse_id": plan.get("warehouse_id") or "auto",
                "priority": plan.get("priority"),
                "objective": plan.get("objective"),
            }
        )
        if plan.get("rationale"):
            st.caption(plan["rationale"])
    with cols[1]:
        st.markdown("**Scenario selected**")
        st.write(
            {
                "key": scenario.get("key"),
                "name": scenario.get("name"),
                "category": scenario.get("category"),
            }
        )
        if scenario.get("rationale"):
            st.caption(scenario["rationale"])

    # ---- Optimization outcome -------------------------------------------
    opt = decision.get("optimization", {})
    st.markdown("**Optimization outcome**")
    outcome_cols = st.columns(3)
    outcome_cols[0].metric("Invoked", opt.get("invoked", "-"))
    outcome_cols[1].metric("Stored", "Yes" if opt.get("persisted") else "No (what-if)")
    outcome_cols[2].metric("Run id", opt.get("run_id") or "-")
    if opt.get("run_id"):
        st.caption("Run id (copy):")
        st.code(opt["run_id"], language="text")

    # ---- Evaluation verdict + KPIs + improvement -------------------------
    evaluation = decision.get("evaluation", {})
    if evaluation:
        st.markdown("**Evaluation verdict**")
        verdict = evaluation.get("verdict", "unknown")
        headline = evaluation.get("headline", "")
        st.info(f"Verdict: **{verdict}**  -  {headline}")
        kpis = evaluation.get("kpis") or {}
        if kpis:
            run_kpi_cards(kpis)
        improvements = evaluation.get("improvements") or {}
        if improvements:
            improvement_bar(improvements)
        _render_benchmark(evaluation.get("benchmark"))

    # ---- Execution trace (auditable five-agent flow) ---------------------
    st.subheader("Execution trace")
    render_agent_trace(decision.get("trace", {}))

    # ---- Report (markdown/text/json) + exports ---------------------------
    st.subheader("Report")
    report = decision.get("report", {})
    render_report(report, crew_narrative=decision.get("crew_narrative"))
    if report:
        exp_cols = st.columns(2)
        with exp_cols[0]:
            download_report_markdown(report, key="agent_report_md")
        with exp_cols[1]:
            download_report_json(report, key="agent_report_json")


def _render_benchmark(benchmark: dict | None) -> None:
    """Show the optional 'vs normal' benchmark deltas, if the crew produced them."""
    if not benchmark:
        return
    st.markdown("**Benchmark vs. 'normal'**")
    cols = st.columns(3)
    cols[0].metric("Cost delta", benchmark.get("cost_delta", "-"))
    cols[1].metric("Distance delta (km)", benchmark.get("distance_delta_km", "-"))
    cols[2].metric("Stockouts delta", benchmark.get("stockouts_delta", "-"))


def _scenario_keys(client: APIClient) -> list[str]:
    """Scenario keys for the override box (empty if the catalog is unavailable)."""
    try:
        catalog = client.get_scenarios()
        return [s.get("key") for s in catalog.get("scenarios", []) if s.get("key")]
    except APIError:
        return []
