"""
============================================================================
CHARTS
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Draws the dashboard charts with Plotly Express over data the API already
  produced. The charts cover the core operational metrics:

    1. Cost by scenario            5. Orders fulfilled by scenario
    2. Distance by scenario        6. Stockouts by scenario
    3. Vehicle utilization by      7. Runs over time (if created_at exists)
       scenario                    8. Improvement percentages (if evaluation
    4. Runtime by optimizer           data exists)

CHARTS VISUALISE - THEY DO NOT COMPUTE (presentation-layer rule)
----------------------------------------------------
  Every per-run KPI (total_cost, travel_distance_km, vehicle_utilization, ...)
  is computed ONCE by the execution-layer metrics code and stored. These charts only
  ARRANGE those stored values for the eye - grouping runs by scenario/optimizer
  and showing the AVERAGE for readability is a display choice, not a new metric.
  The captions say so explicitly, so nothing is presented as a "backend number"
  that the dashboard actually derived.

INPUT
-----
  Most charts take a pandas DataFrame of history rows (built by
  tables.history_to_dataframe from GET /optimization/history). Each function
  degrades gracefully: an empty or column-less frame shows a friendly note
  instead of raising.
============================================================================
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.config import get_settings

# A single, calm color for the bar charts so the dashboard reads as one system.
_BAR_COLOR = "#2E86C1"


# ===========================================================================
# GENERIC BAR-BY-CATEGORY  (the shared engine behind most charts)
# ===========================================================================
def _bar_by_category(
    df: pd.DataFrame,
    *,
    value_col: str,
    category_col: str,
    title: str,
    y_title: str,
    as_percent: bool = False,
    agg: str = "mean",
) -> None:
    """
    Draw one bar chart: the `agg` (default mean) of `value_col` grouped by
    `category_col`. `as_percent` multiplies a 0..1 fraction by 100 for display.

    Grouping + averaging here is purely for READABILITY - the underlying KPI
    values were computed by the backend.
    """
    if df is None or df.empty or value_col not in df.columns or category_col not in df.columns:
        st.info(f"No data yet for '{title}'. Run or store some optimizations first.")
        return

    # Drop rows where the value is missing, then aggregate for display.
    frame = df[[category_col, value_col]].dropna()
    if frame.empty:
        st.info(f"No data yet for '{title}'.")
        return

    grouped = getattr(frame.groupby(category_col)[value_col], agg)().reset_index()
    if as_percent:
        grouped[value_col] = grouped[value_col] * 100.0

    grouped = grouped.sort_values(value_col, ascending=False)

    fig = px.bar(
        grouped,
        x=category_col,
        y=value_col,
        title=title,
        labels={category_col: category_col.replace("_", " ").title(), value_col: y_title},
    )
    fig.update_traces(marker_color=_BAR_COLOR)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=340)
    st.plotly_chart(fig, width="stretch")


# ===========================================================================
# THE NAMED CHARTS  (thin wrappers over the engine above)
# ===========================================================================
def cost_by_scenario(df: pd.DataFrame) -> None:
    """1. Average total cost grouped by scenario."""
    _bar_by_category(df, value_col="total_cost", category_col="scenario",
                     title="Average cost by scenario", y_title="Avg cost")


def distance_by_scenario(df: pd.DataFrame) -> None:
    """2. Average travel distance (km) grouped by scenario."""
    _bar_by_category(df, value_col="travel_distance_km", category_col="scenario",
                     title="Average distance by scenario", y_title="Avg distance (km)")


def utilization_by_scenario(df: pd.DataFrame) -> None:
    """3. Average vehicle utilization (shown as %) grouped by scenario."""
    _bar_by_category(df, value_col="vehicle_utilization", category_col="scenario",
                     title="Average vehicle utilization by scenario",
                     y_title="Avg utilization (%)", as_percent=True)


def runtime_by_optimizer(df: pd.DataFrame) -> None:
    """4. Average solver runtime (ms) grouped by optimizer."""
    _bar_by_category(df, value_col="runtime_ms", category_col="optimizer",
                     title="Average runtime by optimizer", y_title="Avg runtime (ms)")


def orders_by_scenario(df: pd.DataFrame) -> None:
    """5. Average orders fulfilled grouped by scenario."""
    _bar_by_category(df, value_col="orders_fulfilled", category_col="scenario",
                     title="Average orders fulfilled by scenario", y_title="Avg orders")


def stockouts_by_scenario(df: pd.DataFrame) -> None:
    """6. Average stockouts grouped by scenario."""
    _bar_by_category(df, value_col="stockouts", category_col="scenario",
                     title="Average stockouts by scenario", y_title="Avg stockouts")


def runs_over_time(df: pd.DataFrame) -> None:
    """
    7. A timeline of runs, only if the rows carry a usable created_at.

    Plots each run's total_cost against its creation time so a viewer can see
    activity and cost trend over time. It does not resample or forecast - it
    just places the stored runs on a time axis.
    """
    if df is None or df.empty or "created_at" not in df.columns:
        st.info("No timestamped runs yet for the 'runs over time' chart.")
        return

    frame = df.copy()
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["created_at"]).sort_values("created_at")
    if frame.empty:
        st.info("No timestamped runs yet for the 'runs over time' chart.")
        return

    color_col = "scenario" if "scenario" in frame.columns else None
    fig = px.scatter(
        frame,
        x="created_at",
        y="total_cost",
        color=color_col,
        title="Runs over time (cost per run)",
        labels={"created_at": "Created at", "total_cost": "Total cost"},
    )
    fig.update_traces(mode="markers+lines") if color_col is None else None
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=340)
    st.plotly_chart(fig, width="stretch")


def improvement_bar(evaluation: dict, *, title: str = "Comparison with Baseline") -> None:
    """
    8. The before-vs-after improvement percentages for ONE run's evaluation.

    `evaluation` is a run's evaluation block (already-percent values from the
    evaluation framework). Positive bars are improvements; the values are
    displayed exactly as the backend produced them.
    """
    if not evaluation:
        st.info("No evaluation data for this run (it may have been run with evaluate=false).")
        return

    fields = [
        ("Cost", "cost_reduction_percent"),
        ("Distance", "distance_reduction_percent"),
        ("Inventory", "inventory_reduction_percent"),
        ("Stockouts", "stockout_reduction_percent"),
        ("Late deliveries", "late_delivery_reduction_percent"),
        ("Utilization", "utilization_improvement_percent"),
        ("Orders Fulfilled", "delivery_improvement_percent"),
    ]
    rows = [
        {"metric": label, "improvement_percent": evaluation[key]}
        for label, key in fields
        if isinstance(evaluation.get(key), (int, float))
    ]
    if not rows:
        st.info("No comparable improvement percentages in this run's evaluation.")
        return

    frame = pd.DataFrame(rows)
    # Discrete colours: green for an improvement, red for a regression, and a
    # neutral grey for anything within the "unchanged" band (|x| < 0.5pp).
    bar_colors = [_improvement_color(v) for v in frame["improvement_percent"]]
    fig = px.bar(
        frame,
        x="metric",
        y="improvement_percent",
        title=title,
        labels={"metric": "Metric", "improvement_percent": "Change vs. baseline (%)"},
    )
    fig.update_traces(marker_color=bar_colors)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=360)
    st.plotly_chart(fig, width="stretch")


def _improvement_color(value: float) -> str:
    """Green for an improvement, red for a regression, grey for ~no change."""
    if value >= 0.5:
        return "#27AE60"  # green - better than baseline
    if value <= -0.5:
        return "#C0392B"  # red - worse than baseline
    return "#9AA0A6"      # neutral grey - unchanged


def limit_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trim a frame to the configured chart row limit so a very large history never
    renders a slow/unreadable chart. Returns the newest rows when a created_at
    is present. A visible caption elsewhere notes when trimming happens.
    """
    settings = get_settings()
    if df is None or len(df) <= settings.chart_row_limit:
        return df
    if "created_at" in df.columns:
        return df.sort_values("created_at", ascending=False).head(settings.chart_row_limit)
    return df.head(settings.chart_row_limit)
