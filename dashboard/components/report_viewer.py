"""
============================================================================
REPORT VIEWER  (Week 8, Part 11)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Displays the Week 7 Reporting Agent's output the way it was produced - the
  SAME report rendered three ways - using tabs:

        Markdown | Text | JSON

  It also lists the report's recommendations and future improvements, and (when
  present) the optional CrewAI natural-language narrative.

THE DASHBOARD RENDERS THE REPORT - IT DOES NOT WRITE ONE (Week 8 rule)
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


def render_report(report: dict, *, crew_narrative: str | None = None) -> None:
    """
    Render an agent report with Markdown | Text | JSON tabs, then its action
    lists and any optional CrewAI narrative.
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

    _render_action_lists(report)

    # The optional Week 7 crewai narrative (only present in the LLM mode).
    if crew_narrative:
        st.subheader("CrewAI narrative")
        st.markdown(crew_narrative)


def _render_action_lists(report: dict) -> None:
    """Show the recommendations and future-improvements lists side by side."""
    recommendations = report.get("recommendations") or []
    future = report.get("future_improvements") or []
    if not recommendations and not future:
        return

    cols = st.columns(2)
    with cols[0]:
        st.subheader("Recommendations")
        if recommendations:
            for item in recommendations:
                st.markdown(f"- {item}")
        else:
            st.caption("None provided.")
    with cols[1]:
        st.subheader("Future improvements")
        if future:
            for item in future:
                st.markdown(f"- {item}")
        else:
            st.caption("None provided.")
