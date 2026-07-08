"""
============================================================================
TABLES  (Week 8)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Turns API list responses into clean, readable tables:

    * history_to_dataframe(items)      -> a tidy pandas DataFrame of stored runs
      (the flat KPI columns only), reused by the tables AND the charts.
    * render_history_table(df)         -> a formatted, sortable history table.
    * render_scenario_table(scenarios) -> the scenario catalog as a table.

  It shapes and formats data the backend already produced - it never computes a
  KPI. Percentages that arrive as 0..1 fractions (utilization) are shown as real
  percentages, matching the KPI-card rule.
============================================================================
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

# The flat columns we lift out of each history row for the table/charts. These
# mirror the Week 6 OptimizationRunResponse scalar fields (no nested dicts).
_HISTORY_COLUMNS = [
    "run_id",
    "created_at",
    "scenario",
    "optimizer",
    "warehouse_id",
    "success",
    "solver_status",
    "total_cost",
    "travel_distance_km",
    "vehicle_utilization",
    "warehouse_utilization",
    "inventory_holding_cost",
    "stockouts",
    "late_deliveries",
    "orders_fulfilled",
    "runtime_ms",
    "vehicles_used",
    "num_constraints",
    "num_variables",
]


def history_to_dataframe(items: list[dict]) -> pd.DataFrame:
    """
    Build a tidy DataFrame from GET /optimization/history `items`.

    Only the flat scalar columns are kept (the nested metrics/evaluation/details
    dicts are left out of the table view). Missing columns are tolerated, so an
    older/leaner row set still renders.
    """
    if not items:
        return pd.DataFrame(columns=_HISTORY_COLUMNS)
    frame = pd.DataFrame(items)
    # Keep only the known columns that are actually present, in a stable order.
    present = [c for c in _HISTORY_COLUMNS if c in frame.columns]
    return frame[present].copy()


def render_history_table(df: pd.DataFrame) -> None:
    """
    Render the history as a formatted table.

    Utilization columns (0..1) are shown as percentages via Streamlit's
    column_config; costs/distances are given sensible number formats. The raw
    frame is untouched (formatting is display-only); callers still export the
    raw values.
    """
    if df is None or df.empty:
        st.info("No stored optimization runs match the current filters.")
        return

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "run_id": st.column_config.TextColumn("Run id", width="medium"),
            "created_at": st.column_config.DatetimeColumn("Created at", format="YYYY-MM-DD HH:mm"),
            "vehicle_utilization": st.column_config.NumberColumn("Vehicle util.", format="%.1f%%"),
            "warehouse_utilization": st.column_config.NumberColumn("Warehouse util.", format="%.1f%%"),
            "total_cost": st.column_config.NumberColumn("Total cost", format="%.2f"),
            "travel_distance_km": st.column_config.NumberColumn("Distance (km)", format="%.1f"),
            "inventory_holding_cost": st.column_config.NumberColumn("Holding cost", format="%.2f"),
            "runtime_ms": st.column_config.NumberColumn("Runtime (ms)", format="%.1f"),
        },
    )


def scenario_dataframe(scenarios: list[dict]) -> pd.DataFrame:
    """Build a DataFrame from a scenario catalog list ({key,name,category,description})."""
    if not scenarios:
        return pd.DataFrame(columns=["key", "name", "category", "description"])
    return pd.DataFrame(scenarios)[["key", "name", "category", "description"]]


def render_scenario_table(scenarios: list[dict]) -> None:
    """Render the scenario catalog (GET /optimization/scenarios) as a table."""
    frame = scenario_dataframe(scenarios)
    if frame.empty:
        st.info("The scenario catalog is empty or unavailable.")
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "key": st.column_config.TextColumn("Key"),
            "name": st.column_config.TextColumn("Name"),
            "category": st.column_config.TextColumn("Category"),
            "description": st.column_config.TextColumn("Description", width="large"),
        },
    )
