"""
============================================================================
OVERVIEW PAGE  (Week 8, Part 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  The at-a-glance summary of the whole platform:
    * the project title + a short architecture summary,
    * the aggregate KPI cards (from GET /optimization/metrics): stored runs,
      total/average cost, total distance, average vehicle utilization, total
      orders fulfilled, total stockouts, average runtime,
    * runs per scenario (straight from the metrics response) and runs per
      optimizer (counted from the history rows, purely for display),
    * a plain-text architecture diagram for both the direct and agent flows.

WHERE THE NUMBERS COME FROM (no computation here)
-------------------------------------------------
  GET /optimization/metrics gives every aggregate KPI and runs_per_scenario. The
  only thing counted client-side is "runs per optimizer" - a display tally of
  the optimizer column across the returned history rows (counting rows is not a
  KPI computation). It is clearly labelled as covering the most recent runs.
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.agent_trace import render_agent_flow
from dashboard.components.charts import limit_rows, runs_over_time, runtime_by_optimizer
from dashboard.components.kpi_cards import aggregate_kpi_cards
from dashboard.components.tables import history_to_dataframe


DIRECT_FLOW = """User
 -> Dashboard (Streamlit)
 -> FastAPI
 -> Execution Service (Week 6)
 -> Optimization Engine (Week 5, OR-Tools)
 -> PostgreSQL (Week 3)"""

AGENT_FLOW = """User
 -> Dashboard (Streamlit)
 -> /agents/decide (Week 7)
 -> Coordinator
 -> Planner -> Scenario -> Optimization -> Evaluation -> Reporting
 -> Execution Service (Week 6) -> Optimization Engine (Week 5) -> PostgreSQL"""


def render(client: APIClient) -> None:
    """Render the Overview page."""
    st.header("Overview")
    st.caption(
        "A single-glance view of the platform: how many optimizations have been "
        "run, what they cost, how well the fleet was used, and how the autonomous "
        "agents fit in. Every number below comes from the backend APIs."
    )

    # ---- The aggregate KPI cards (GET /optimization/metrics) --------------
    st.subheader("Key performance indicators")
    try:
        metrics = client.get_metrics()
        aggregate_kpi_cards(metrics)
    except APIError as exc:
        st.warning(f"Could not load aggregate KPIs. {exc.message}")
        metrics = {}

    # ---- One history fetch, reused for the breakdowns and the trends ------
    df = None
    try:
        page = client.get_history(page=1, page_size=client.settings.max_page_size,
                                  sort_by="created_at", sort_dir="desc")
        df = limit_rows(history_to_dataframe(page.get("items", [])))
    except APIError as exc:
        st.info(f"Could not load recent runs for the breakdowns. {exc.message}")

    # ---- Runs per scenario / per optimizer -------------------------------
    st.subheader("Activity breakdown")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Runs per scenario**")
        runs_per_scenario = (metrics or {}).get("runs_per_scenario") or {}
        if runs_per_scenario:
            st.bar_chart(runs_per_scenario)
        else:
            st.info("No stored runs yet.")

    with col_right:
        st.markdown("**Runs per optimizer** (recent runs)")
        runs_per_optimizer = _count_runs_per_optimizer(df)
        if runs_per_optimizer:
            st.bar_chart(runs_per_optimizer)
            st.caption(
                "Counted from the most recent history rows for display only - the "
                "KPI values themselves are computed by the backend."
            )
        else:
            st.info("No stored runs yet.")

    # ---- Trends over the recent runs -------------------------------------
    if df is not None and not df.empty:
        st.subheader("Trends")
        trend_cols = st.columns(2)
        with trend_cols[0]:
            runtime_by_optimizer(df)
        with trend_cols[1]:
            runs_over_time(df)

    # ---- The five-agent flow legend --------------------------------------
    st.subheader("Autonomous agent workflow")
    render_agent_flow()
    st.caption(
        "The Week 7 crew turns a plain-English request into a recorded decision. "
        "See the Agent Decisions page to run one, and the trace it produces."
    )

    # ---- Architecture summary + text diagrams ----------------------------
    st.subheader("System architecture")
    st.markdown(
        "The dashboard is a **presentation layer only**. It reads and writes "
        "through the existing FastAPI endpoints and never calls OR-Tools or the "
        "database directly. Two request flows sit behind it:"
    )
    diagram_cols = st.columns(2)
    with diagram_cols[0]:
        st.markdown("**Direct optimization flow**")
        st.code(DIRECT_FLOW, language="text")
    with diagram_cols[1]:
        st.markdown("**Autonomous agent flow**")
        st.code(AGENT_FLOW, language="text")


def _count_runs_per_optimizer(df) -> dict:
    """
    Tally runs by optimizer from an already-fetched history frame (display only).

    The backend's /optimization/metrics does not break down by optimizer, so we
    count the optimizer column across the recent runs. This is a simple row
    count, not a KPI computation, and it is labelled as such in the UI.
    """
    if df is None or df.empty or "optimizer" not in df.columns:
        return {}
    counts = df["optimizer"].fillna("unknown").value_counts()
    return {str(k): int(v) for k, v in counts.items()}
