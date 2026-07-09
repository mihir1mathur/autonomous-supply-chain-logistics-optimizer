"""
============================================================================
AGENT TRACE VIEWER
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Visualises the agent EXECUTION TRACE - the step-by-step record of what each
  of the five agents did during one autonomous decision. It shows the flow

        PlannerAgent -> ScenarioAgent -> OptimizationAgent
                     -> EvaluationAgent -> ReportingAgent

  and, for each step: the agent name, the action, success/failure, how long it
  took, a one-line summary, and any error.

WHY THIS MATTERS
----------------
  This is the single most important view for demonstrating the agent autonomy:
  it proves the agent workflow is AUDITABLE. A viewer can see exactly which
  agent decided what, in what order, and whether every step succeeded - the same
  trace the /agents API returns, simply drawn for a human.

INPUT
-----
  A `trace` dict as returned by the API:
      {"steps": [{"agent","action","success","duration_ms","summary","error"}...],
       "total_ms": <float>, "all_succeeded": <bool>}
  Missing/empty traces are handled gracefully.
============================================================================
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.utils.formatting import format_ms

# The canonical five-agent order (used to draw the flow line even before a run).
AGENT_FLOW = [
    "PlannerAgent",
    "ScenarioAgent",
    "OptimizationAgent",
    "EvaluationAgent",
    "ReportingAgent",
]

# Concise, business-friendly summaries shown in the trace table - so the view
# reads like an audit log instead of exposing the backend's internal one-liners.
_CONCISE_SUMMARY = {
    "PlannerAgent": "Created execution plan",
    "ScenarioAgent": "Selected operating scenario",
    "OptimizationAgent": "Generated optimized solution",
    "EvaluationAgent": "Compared against baseline",
    "ReportingAgent": "Generated decision report",
}


def _concise_summary(step: dict, scenario_name: str | None) -> str:
    """A short business summary for one trace step (never a raw backend string)."""
    if not step.get("success"):
        return "Did not complete"
    agent = step.get("agent")
    if agent == "ScenarioAgent" and scenario_name:
        return f"Selected {scenario_name}"
    return _CONCISE_SUMMARY.get(agent, "Completed step")


def render_agent_flow(steps: list[dict] | None = None) -> None:
    """
    Draw the five-agent flow as a single line with a status mark per agent.

    With `steps` supplied, each agent shows a check (succeeded), a cross
    (failed), or a dot (did not run). With no steps, it shows the plain expected
    flow - handy as a legend on the Overview/Agent pages.
    """
    status_by_agent = {}
    for step in steps or []:
        status_by_agent[step.get("agent")] = step.get("success")

    parts = []
    for agent in AGENT_FLOW:
        if agent in status_by_agent:
            mark = "OK" if status_by_agent[agent] else "X"
        else:
            mark = "." if steps else ""
        label = agent.replace("Agent", "")
        parts.append(f"**{label}** {mark}".strip())
    st.markdown(" &nbsp;->&nbsp; ".join(parts))


def render_agent_trace(trace: dict, *, scenario_name: str | None = None) -> None:
    """
    Render the full trace: the flow line, a headline (total time + overall
    result), a per-step table, and expandable error details for any failure.

    `scenario_name`, when supplied, lets the Scenario step read "Selected
    <scenario name>" instead of a generic line.
    """
    trace = trace or {}
    steps = trace.get("steps", [])

    render_agent_flow(steps)

    if not steps:
        st.info("No execution trace to show yet. Run an agent decision first.")
        return

    # Headline: total time and whether every step succeeded.
    total_ms = trace.get("total_ms")
    all_ok = trace.get("all_succeeded")
    cols = st.columns(2)
    cols[0].metric("Total agent time", format_ms(total_ms))
    cols[1].metric("All steps succeeded", "Yes" if all_ok else "No")

    # A clean per-step table. The agent name is shown without the "Agent" suffix
    # and the summary is a concise business line (not the raw backend string).
    rows = []
    for i, step in enumerate(steps, start=1):
        rows.append(
            {
                "#": i,
                "Agent": str(step.get("agent", "?")).replace("Agent", ""),
                "Action": str(step.get("action", "")).replace("_", " ").title(),
                "Status": "OK" if step.get("success") else "FAILED",
                "Duration": format_ms(step.get("duration_ms")),
                "Summary": _concise_summary(step, scenario_name),
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", width="small"),
            "Summary": st.column_config.TextColumn("Summary", width="large"),
        },
    )

    # Surface any errors prominently (an autonomous run should fail LOUDLY).
    failed = [s for s in steps if not s.get("success")]
    if failed:
        st.error(f"{len(failed)} step(s) failed - see details below.")
        for step in failed:
            with st.expander(f"Error in {step.get('agent', 'agent')}"):
                st.write(step.get("error") or "(no error message provided)")
