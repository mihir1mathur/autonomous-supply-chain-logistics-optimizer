"""
============================================================================
OVERVIEW PAGE
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

from pathlib import Path

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.agent_trace import render_agent_flow
from dashboard.components.charts import limit_rows, runs_over_time, runtime_by_optimizer
from dashboard.components.kpi_cards import aggregate_kpi_cards
from dashboard.components.tables import history_to_dataframe

# The generated architecture diagram. It is rendered as an image because
# Streamlit does not natively render Mermaid; the README uses the same diagram
# (as GitHub-native Mermaid plus this PNG).
_ARCH_IMAGE = Path(__file__).resolve().parents[2] / "docs" / "images" / "system_architecture.png"

# Concise request flows for the two execution modes (presentation text only).
DIRECT_FLOW = "User\n→ Streamlit\n→ FastAPI\n→ Execution Service\n→ OR-Tools\n→ PostgreSQL"
AGENT_FLOW = (
    "User\n→ Streamlit\n→ Coordinator\n→ Planner\n→ Scenario\n→ Optimization\n"
    "→ Evaluation\n→ Reporting\n→ Execution Service\n→ OR-Tools\n→ PostgreSQL"
)

# System design highlights: (title, one-line explanation).
_DESIGN_HIGHLIGHTS = [
    ("Layered Architecture", "Five independent layers, each with a single clear role."),
    ("Separation of Concerns", "Every module owns one responsibility and nothing more."),
    ("Multi-Agent Orchestration", "Five specialized agents collaborate on each decision."),
    ("REST API Communication", "All traffic flows over well-defined FastAPI endpoints."),
    ("Deterministic Optimization", "Google OR-Tools produces reproducible optimization plans."),
    ("Persistent History", "Every optimization run can be stored, retrieved, and audited."),
    ("Modular Components", "Layers, agents, and optimizers are independently replaceable."),
    ("UI Independent of Logic", "The dashboard only calls APIs — never the solver or database."),
]

# Technology stack: (area, technology).
_TECH_STACK = [
    ("Presentation", "Streamlit"),
    ("Backend", "FastAPI"),
    ("Optimization", "Google OR-Tools"),
    ("Database", "PostgreSQL"),
    ("Language", "Python"),
    ("Visualization", "Plotly"),
    ("AI Orchestration", "Custom Multi-Agent Coordinator"),
]

# Architecture principles: (title, one-line explanation).
_ARCH_PRINCIPLES = [
    ("Presentation Layer", "The UI never calls OR-Tools directly."),
    ("Backend APIs", "All requests flow through FastAPI."),
    ("Agent Independence", "Each agent has one clearly defined responsibility."),
    ("Execution Service", "A single entry point into optimization."),
    ("Persistence", "Every optimization run can be stored independently."),
    ("Scalability", "New agents and optimizers can be added without touching existing ones."),
]


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
        "The autonomous multi-agent engine turns a plain-English request into a recorded decision. "
        "See the Agent Decisions page to run one, and the trace it produces."
    )

    # ---- Architecture (diagram, modes, highlights, stack, principles) ----
    st.divider()
    _render_architecture()


def _render_architecture() -> None:
    """The recruiter-facing architecture overview: diagram, modes, highlights, stack, principles."""
    st.subheader("System Architecture")
    st.markdown(
        "The platform is built as **five clean layers**. The Streamlit dashboard is a "
        "**presentation layer only** — every request is routed through FastAPI, where the "
        "business logic lives. From there, the autonomous multi-agent system coordinates "
        "planning, scenario selection, optimization, evaluation, and reporting, before the "
        "Execution Service runs Google OR-Tools and persists results in PostgreSQL."
    )

    if _ARCH_IMAGE.exists():
        st.image(
            str(_ARCH_IMAGE),
            width="stretch",
            caption="Five-layer architecture — presentation, application, autonomous agents, "
            "optimization, and persistence.",
        )

    # ---- The two execution modes -----------------------------------------
    st.markdown("#### Execution Modes")
    mode_cols = st.columns(2)
    with mode_cols[0]:
        with st.container(border=True):
            st.markdown("**⚡ Direct Optimization Flow**")
            st.caption("Used when the user directly selects an optimizer and scenario.")
            st.code(DIRECT_FLOW, language="text")
            st.caption("**Purpose:** fast, deterministic optimization.")
    with mode_cols[1]:
        with st.container(border=True):
            st.markdown("**🤖 Autonomous Agent Flow**")
            st.caption("Used when the user submits a natural-language business request.")
            st.code(AGENT_FLOW, language="text")
            st.caption(
                "**Purpose:** turn a business request into an optimized plan, evaluate it "
                "against a baseline, and produce an executive decision report."
            )

    # ---- System design highlights ----------------------------------------
    st.divider()
    st.subheader("System Design Highlights")
    _render_point_columns(_DESIGN_HIGHLIGHTS, marker="✓ ")

    # ---- Technology stack ------------------------------------------------
    st.divider()
    st.subheader("Technology Stack")
    _render_point_columns([(area, tech) for area, tech in _TECH_STACK], separator=" · ")

    # ---- Architecture principles -----------------------------------------
    st.divider()
    st.subheader("Architecture Principles")
    _render_point_columns(_ARCH_PRINCIPLES)


def _render_point_columns(points: list, *, marker: str = "", separator: str = " — ") -> None:
    """Lay out (title, detail) pairs as bold-titled lines across two balanced columns."""
    columns = st.columns(2)
    half = (len(points) + 1) // 2
    for column, chunk in zip(columns, (points[:half], points[half:])):
        with column:
            for title, detail in chunk:
                st.markdown(f"{marker}**{title}**{separator}{detail}")


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
