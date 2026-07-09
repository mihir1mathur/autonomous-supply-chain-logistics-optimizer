"""
============================================================================
KPI CARDS
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Renders the headline numbers as "KPI cards" - a big value with a short label
  (Streamlit's st.metric). One reusable card function, plus convenience
  functions that lay out a whole row of cards from an API response.

WHERE THE NUMBERS COME FROM (no computation here)
-------------------------------------------------
  Every value is read straight from an API response:
    * GET /optimization/metrics  -> the aggregate KPIs (run count, total /
      average cost, total distance, average vehicle utilization, total orders,
      total stockouts, average runtime).
    * a single run's `metrics`   -> the twelve RunMetrics of one run.
  This component does NOT add, average, or derive anything - it only FORMATS and
  DISPLAYS. That keeps the presentation-layer rule (visualize/format, never
  compute) intact: KPIs are computed once, in the execution-layer
  metrics/evaluation code, and merely shown here.

FORMATTING RULE
  Utilization is a 0..1 fraction in the API, so it is shown with
  fraction_to_percent() as a real percentage (76.7%), never as "0.77".
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.utils.formatting import (
    fraction_to_percent,
    format_currency,
    format_distance_km,
    format_int,
    format_ms,
    format_percent_value,
)


# ===========================================================================
# THE ONE REUSABLE CARD
# ===========================================================================
def kpi_card(column, label: str, value: str, help_text: str | None = None) -> None:
    """
    Render one KPI card (a label + a big value) into a given Streamlit column.

    `value` is expected to be an ALREADY-FORMATTED string (e.g. "76.7%",
    "$1,234.50"), so the caller controls formatting and this stays presentation-
    only. `help_text` shows the little "?" tooltip explaining the metric.
    """
    with column:
        st.metric(label=label, value=value, help=help_text)


def kpi_row(cards: list[tuple[str, str, str | None]]) -> None:
    """
    Lay out a row of KPI cards. `cards` is a list of (label, value, help) tuples.
    The row splits into as many equal columns as there are cards.
    """
    if not cards:
        return
    columns = st.columns(len(cards))
    for column, (label, value, help_text) in zip(columns, cards):
        kpi_card(column, label, value, help_text)


# ===========================================================================
# READY-MADE ROWS FROM API RESPONSES
# ===========================================================================
def aggregate_kpi_cards(metrics: dict) -> None:
    """
    Render the aggregate KPI cards from a GET /optimization/metrics response.

    Shown across two rows so the labels stay readable:
      Row 1: run count, total cost, average cost, total distance
      Row 2: avg vehicle utilization, orders fulfilled, stockouts, avg runtime
    """
    metrics = metrics or {}

    kpi_row(
        [
            ("Stored runs", format_int(metrics.get("run_count")),
             "How many optimization runs are stored (GET /optimization/metrics)."),
            ("Total cost", format_currency(metrics.get("total_cost")),
             "Sum of total_cost across all stored runs (simulated cost units)."),
            ("Average cost", format_currency(metrics.get("average_cost")),
             "Mean total_cost per stored run."),
            ("Total distance", format_distance_km(metrics.get("total_distance_km")),
             "Sum of travel_distance_km across all stored runs."),
        ]
    )
    kpi_row(
        [
            ("Avg vehicle utilization",
             fraction_to_percent(metrics.get("average_vehicle_utilization")),
             "Mean vehicle_utilization across runs (stored 0..1, shown as %)."),
            ("Orders fulfilled", format_int(metrics.get("total_orders_fulfilled")),
             "Sum of orders_fulfilled across all stored runs."),
            ("Stockouts", format_int(metrics.get("total_stockouts")),
             "Sum of stockouts across all stored runs (lower is better)."),
            ("Avg runtime", format_ms(metrics.get("average_runtime_ms")),
             "Mean solver runtime per run."),
        ]
    )


def run_kpi_cards(metrics: dict) -> None:
    """
    Render the KPI cards for ONE run, from its `metrics` block (the twelve
    RunMetrics). Used on the history drill-down and the agent decision page.
    """
    metrics = metrics or {}

    kpi_row(
        [
            ("Total cost", format_currency(metrics.get("total_cost")),
             "The plan's total cost (simulated cost units)."),
            ("Travel distance", format_distance_km(metrics.get("travel_distance_km")),
             "Total road distance of the plan (km, with the winding factor)."),
            ("Vehicle utilization", fraction_to_percent(metrics.get("vehicle_utilization")),
             "Share of loaded vehicle capacity used (0..1, shown as %)."),
            ("Warehouse utilization", fraction_to_percent(metrics.get("warehouse_utilization")),
             "Share of warehouse capacity used (0..1, shown as %)."),
        ]
    )
    kpi_row(
        [
            ("Orders fulfilled", format_int(metrics.get("orders_fulfilled")),
             "Shipments the plan serves."),
            ("Stockouts", format_int(metrics.get("stockouts")),
             "Demands that could not be met from stock (lower is better)."),
            ("Late deliveries", format_int(metrics.get("late_deliveries")),
             "Shipments flagged at risk of being late (a documented proxy)."),
            ("Runtime", format_ms(metrics.get("optimization_runtime_ms")),
             "How long the solver took."),
        ]
    )


def evaluation_kpi_cards(evaluation: dict) -> None:
    """
    Render the before-vs-after improvement cards from a run's `evaluation` block
    (the evaluation percentages). These are ALREADY percentages, so they
    use format_percent_value(signed=True) to show a clear "+/-".
    """
    evaluation = evaluation or {}

    kpi_row(
        [
            ("Cost reduction",
             format_percent_value(evaluation.get("cost_reduction_percent"), signed=True),
             "How much cheaper the optimized plan is vs. the naive baseline."),
            ("Distance reduction",
             format_percent_value(evaluation.get("distance_reduction_percent"), signed=True),
             "How much shorter the optimized plan is vs. the baseline."),
            ("Utilization improvement",
             format_percent_value(evaluation.get("utilization_improvement_percent"), signed=True),
             "How much better vehicle utilization is vs. the baseline."),
            ("Delivery improvement",
             format_percent_value(evaluation.get("delivery_improvement_percent"), signed=True),
             "Improvement in on-time / fulfilled deliveries vs. the baseline."),
        ]
    )
