"""
============================================================================
OPTIMIZATION HISTORY PAGE  (Week 8, Part 7)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  A browsable table of past optimization runs (GET /optimization/history) with:
    * filters (scenario, optimizer, solver status, warehouse id),
    * sorting (created_at, total cost, vehicle utilization, runtime) + paging,
    * a CSV export of the current page,
    * a drill-down: pick one run and see its KPIs, its before-vs-after
      evaluation, the scenario changes applied, and its metadata (run_id,
      created_at, optimizer, scenario, solver status), plus a JSON export and a
      copy-friendly run_id.

BACKEND DOES THE WORK
---------------------
  All filtering/sorting/paging is done by the Week 6 history endpoint; this page
  only collects the controls (components/filters.py) and displays the rows
  (components/tables.py). The drill-down re-reads the single run through
  GET /optimization/{run_id} so it always shows the stored record of truth.
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.charts import improvement_bar
from dashboard.components.filters import history_filters
from dashboard.components.kpi_cards import run_kpi_cards
from dashboard.components.tables import history_to_dataframe, render_history_table
from dashboard.utils.export import download_history_csv, download_run_json
from dashboard.utils.formatting import format_datetime


def render(client: APIClient) -> None:
    """Render the Optimization History page."""
    st.header("Optimization History")
    st.caption(
        "Every stored optimization run, newest first. Filter and sort on the "
        "backend, then drill into a single run to see its KPIs and evaluation."
    )

    # ---- Filter options: scenario keys + solver statuses seen in the data --
    scenario_keys = _scenario_keys(client)
    solver_statuses = _recent_solver_statuses(client)

    # ---- The filter/sort/paging controls ---------------------------------
    params = history_filters(scenario_keys, solver_statuses=solver_statuses)

    # ---- Fetch the page of runs ------------------------------------------
    try:
        page = client.get_history(**params)
    except APIError as exc:
        st.error(f"Could not load the optimization history. {exc.message}")
        return

    items = page.get("items", [])
    pagination = page.get("pagination", {})

    # A one-line pagination summary.
    total = pagination.get("total", len(items))
    page_no = pagination.get("page", params["page"])
    total_pages = pagination.get("total_pages", 1)
    st.write(f"Showing page **{page_no}** of **{total_pages}** - **{total}** run(s) match.")

    # ---- The table + CSV export ------------------------------------------
    df = history_to_dataframe(items)
    render_history_table(df)
    if items:
        download_history_csv(items, key="history_csv")

    if not items:
        return

    # ---- Drill-down into one run -----------------------------------------
    st.subheader("Run details")
    run_ids = [row.get("run_id") for row in items if row.get("run_id")]
    selected = st.selectbox("Select a run to inspect", run_ids, index=0)
    if selected:
        _render_run_details(client, selected)


def _render_run_details(client: APIClient, run_id: str) -> None:
    """Fetch one run by id and show its metadata, KPIs, evaluation, and changes."""
    try:
        run = client.get_run(run_id)
    except APIError as exc:
        st.error(f"Could not load run {run_id}. {exc.message}")
        return

    # Metadata row (with a copy-friendly run_id).
    meta_cols = st.columns(4)
    meta_cols[0].metric("Scenario", run.get("scenario") or "-")
    meta_cols[1].metric("Optimizer", run.get("optimizer") or "-")
    meta_cols[2].metric("Solver status", run.get("solver_status") or "-")
    meta_cols[3].metric("Created at", format_datetime(run.get("created_at")))

    st.caption("Run id (click the copy icon to copy):")
    st.code(run.get("run_id", run_id), language="text")

    # KPIs: prefer the nested `metrics` dict; fall back to the flat columns.
    st.markdown("**Key performance indicators**")
    metrics = run.get("metrics") or _flat_metrics(run)
    run_kpi_cards(metrics)

    # Before-vs-after evaluation (if it was computed for this run).
    evaluation = run.get("evaluation")
    if evaluation:
        st.markdown("**Before vs. after evaluation**")
        summary = evaluation.get("summary")
        if summary:
            st.info(summary)
        improvement_bar(evaluation)

    # Scenario changes applied to the inputs (if recorded in details).
    changes = _scenario_changes(run)
    if changes:
        st.markdown("**Scenario changes applied**")
        for change in changes:
            st.markdown(f"- {change}")

    # JSON export of the whole stored run.
    download_run_json(run, filename=f"run_{run_id}.json", key=f"run_json_{run_id}")


# ===========================================================================
# SMALL HELPERS (read-only shaping of API data)
# ===========================================================================
def _scenario_keys(client: APIClient) -> list[str]:
    """Scenario keys for the filter box (empty list if the catalog is down)."""
    try:
        catalog = client.get_scenarios()
        return [s.get("key") for s in catalog.get("scenarios", []) if s.get("key")]
    except APIError:
        return []


def _recent_solver_statuses(client: APIClient) -> list[str]:
    """Distinct solver statuses seen in a recent page (for the filter box)."""
    try:
        page = client.get_history(page=1, page_size=client.settings.max_page_size)
    except APIError:
        return []
    statuses = {row.get("solver_status") for row in page.get("items", []) if row.get("solver_status")}
    return sorted(statuses)


def _flat_metrics(run: dict) -> dict:
    """
    Build a metrics-shaped dict from the flat run columns, used when the nested
    `metrics` field is absent. Pure re-mapping of existing values (no math).
    """
    return {
        "total_cost": run.get("total_cost"),
        "travel_distance_km": run.get("travel_distance_km"),
        "vehicle_utilization": run.get("vehicle_utilization"),
        "warehouse_utilization": run.get("warehouse_utilization"),
        "orders_fulfilled": run.get("orders_fulfilled"),
        "stockouts": run.get("stockouts"),
        "late_deliveries": run.get("late_deliveries"),
        "optimization_runtime_ms": run.get("runtime_ms"),
    }


def _scenario_changes(run: dict) -> list[str]:
    """Pull the human-readable scenario change list out of the run's details."""
    details = run.get("details") or {}
    changes = details.get("scenario_changes")
    if isinstance(changes, list):
        return changes
    return []
