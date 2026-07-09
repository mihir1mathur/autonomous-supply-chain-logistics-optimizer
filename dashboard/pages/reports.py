"""
============================================================================
REPORTS PAGE
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  An executive decision report produced by the autonomous multi-agent crew,
  laid out as a business document rather than raw markdown:

      Execution badge -> Executive Summary -> Key Performance Indicators ->
      Evaluation -> Business Risks -> Recommendations -> Future Roadmap

  The Markdown | Text | JSON renderings and their downloads are preserved (they
  power the exports) inside a collapsible "full report" panel.

WHERE THE REPORT COMES FROM
---------------------------
  * If a decision has been run on the Agent Decisions page, its report is
    remembered (st.session_state) and shown here immediately - no re-run needed.
  * Otherwise, a small inline form generates one via POST /agents/simulate (a
    what-if that is NOT stored), purely so this page has a report to display.

  Either way the dashboard RENDERS an existing report and re-presents the values
  the reporting agent already produced; it never composes a report itself.
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.report_viewer import (
    render_business_risks,
    render_evaluation_report,
    render_execution_badge,
    render_executive_summary,
    render_future_roadmap,
    render_kpi_report_cards,
    render_recommendations,
    render_report,
)
from dashboard.pages.agent_decisions import LAST_DECISION_KEY
from dashboard.utils.export import download_report_json, download_report_markdown


def render(client: APIClient) -> None:
    """Render the Reports page."""
    st.header("Reports")
    st.caption(
        "Executive decision report from the autonomous multi-agent crew — KPI "
        "analytics, baseline evaluation, business risks, and actionable "
        "recommendations for the latest decision."
    )

    decision = st.session_state.get(LAST_DECISION_KEY)

    # If there is no decision yet, offer a quick (non-persisted) generation.
    if not decision:
        decision = _render_quick_generate(client)

    if not decision:
        st.info("No report yet. Generate one above, or run a decision on the Agent Decisions page.")
        return

    report = decision.get("report") or {}
    if not report:
        st.warning("This decision did not include a report.")
        return

    evaluation = decision.get("evaluation") or {}
    kpis = evaluation.get("kpis") or {}

    # ---- Execution mode badge (stored vs. simulated) ---------------------
    render_execution_badge(decision.get("optimization") or {})

    # ---- Executive summary -----------------------------------------------
    st.subheader("Executive Summary")
    render_executive_summary(decision)

    # ---- Key performance indicators --------------------------------------
    st.divider()
    st.subheader("Key Performance Indicators")
    render_kpi_report_cards(kpis)

    # ---- Evaluation (visual indicators) ----------------------------------
    st.divider()
    st.subheader("Evaluation")
    render_evaluation_report(evaluation)

    # ---- Business risks ---------------------------------------------------
    st.divider()
    st.subheader("Business Risks")
    render_business_risks(kpis)

    # ---- Recommendations (exactly one section) ---------------------------
    st.divider()
    st.subheader("Recommendations")
    render_recommendations(report)

    # ---- Future engineering roadmap --------------------------------------
    st.divider()
    st.subheader("Future Engineering Roadmap")
    render_future_roadmap()

    # ---- Exports + raw formats (preserved) -------------------------------
    st.divider()
    export_cols = st.columns(2)
    with export_cols[0]:
        download_report_markdown(report, key="reports_page_md")
    with export_cols[1]:
        download_report_json(report, key="reports_page_json")

    with st.expander("View full report (Markdown · Text · JSON)", expanded=False):
        render_report(
            report,
            crew_narrative=decision.get("crew_narrative"),
            show_recommendations=False,
        )


def _render_quick_generate(client: APIClient) -> dict | None:
    """A tiny form that generates a report via /agents/simulate (not stored)."""
    with st.form("reports_quick_generate"):
        goal = st.text_input(
            "Describe a goal to generate a report",
            value="Summarize a normal-operations optimization and recommend improvements.",
        )
        submitted = st.form_submit_button("Generate Report (What-If, Not Stored)")

    if not submitted:
        return None

    try:
        with st.spinner("Asking the crew for a report..."):
            decision = client.agent_simulate({"goal": goal.strip() or None})
    except APIError as exc:
        st.error(f"Could not generate a report. {exc.message}")
        return None

    # Remember it so the rest of the page (and the Agent page) can reuse it.
    st.session_state[LAST_DECISION_KEY] = decision
    return decision
