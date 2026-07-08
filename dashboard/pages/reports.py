"""
============================================================================
REPORTS PAGE  (Week 8, Part 11)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  The Week 7 Reporting Agent's output, rendered as Markdown | Text | JSON tabs,
  with its recommendations and future improvements - plus Markdown/JSON exports.

WHERE THE REPORT COMES FROM
---------------------------
  * If you have already run a decision on the Agent Decisions page, its report is
    remembered (st.session_state) and shown here immediately - no re-run needed.
  * Otherwise, a small inline form lets you generate one via POST /agents/simulate
    (a what-if that is NOT stored), purely so this page has a report to display.

  Either way, the dashboard RENDERS an existing report; it never composes a new
  report itself (the reporting agent does that on the backend).
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.report_viewer import render_report
from dashboard.pages.agent_decisions import LAST_DECISION_KEY
from dashboard.utils.export import download_report_json, download_report_markdown


def render(client: APIClient) -> None:
    """Render the Reports page."""
    st.header("Reports")
    st.caption(
        "The human-readable report the Reporting Agent produced for the latest "
        "decision, in three formats. Generate one below if you have not run a "
        "decision yet."
    )

    decision = st.session_state.get(LAST_DECISION_KEY)

    # If there is no decision yet, offer a quick (non-persisted) generation.
    if not decision:
        decision = _render_quick_generate(client)

    if not decision:
        st.info("No report yet. Generate one above, or run a decision on the Agent Decisions page.")
        return

    # Small context line about which decision this report belongs to.
    scenario = decision.get("scenario", {}) or {}
    plan = decision.get("plan", {}) or {}
    st.caption(
        f"Report for: optimizer **{plan.get('optimizer', '?')}**, scenario "
        f"**{scenario.get('key', '?')}**, mode **{decision.get('mode', '?')}**."
    )

    report = decision.get("report", {})
    render_report(report, crew_narrative=decision.get("crew_narrative"))

    if report:
        cols = st.columns(2)
        with cols[0]:
            download_report_markdown(report, key="reports_page_md")
        with cols[1]:
            download_report_json(report, key="reports_page_json")


def _render_quick_generate(client: APIClient) -> dict | None:
    """A tiny form that generates a report via /agents/simulate (not stored)."""
    with st.form("reports_quick_generate"):
        goal = st.text_input(
            "Describe a goal to generate a report",
            value="Summarize a normal-operations optimization and recommend improvements.",
        )
        submitted = st.form_submit_button("Generate report (what-if, not stored)")

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
