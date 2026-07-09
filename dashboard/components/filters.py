"""
============================================================================
FILTERS
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE DOES
-------------------
  Renders the filter + sort + paging controls for the Optimization History page
  and returns the user's choices as a plain dict of QUERY PARAMETERS. The page
  hands that dict straight to api_client.get_history(...), so ALL filtering,
  sorting and paging happens on the BACKEND (the history endpoint) - the
  dashboard only collects the inputs.

WHY THE BACKEND DOES THE WORK
-----------------------------
  The OptimizationRunService already supports filter/search/sort/paginate
  over the optimization_runs table. Re-doing any of that in the dashboard would
  duplicate backend logic (not allowed in the presentation layer) and would only ever see one page of
  data. So these controls are pure INPUT widgets.
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.config import get_settings

# The optimizers the platform supports (matches VALID_OPTIMIZERS on the backend).
OPTIMIZERS = ["assignment", "fleet", "routes", "warehouse"]

# The columns the history endpoint can sort by (a subset of its
# sortable_fields), shown with friendly labels. The value is the API field name.
SORT_OPTIONS = {
    "Created at (newest)": ("created_at", "desc"),
    "Created at (oldest)": ("created_at", "asc"),
    "Total cost (low to high)": ("total_cost", "asc"),
    "Total cost (high to low)": ("total_cost", "desc"),
    "Vehicle utilization (high to low)": ("vehicle_utilization", "desc"),
    "Runtime (fast to slow)": ("runtime_ms", "asc"),
}


def history_filters(
    scenario_keys: list[str],
    *,
    solver_statuses: list[str] | None = None,
) -> dict:
    """
    Render the history filter/sort/paging controls and return the chosen query
    parameters as a dict ready for api_client.get_history(**params).

    `scenario_keys` comes from the scenario catalog; `solver_statuses` is an
    optional list of statuses seen in the data (used to build a select box - a
    blank choice means "any"). warehouse_id is a free-text box because there is
    no dedicated catalog endpoint for it.
    """
    settings = get_settings()
    any_label = "(any)"

    with st.expander("Filters & sorting", expanded=True):
        row1 = st.columns(4)
        with row1[0]:
            scenario = st.selectbox("Scenario", [any_label] + sorted(scenario_keys), index=0)
        with row1[1]:
            optimizer = st.selectbox("Optimizer", [any_label] + OPTIMIZERS, index=0)
        with row1[2]:
            statuses = solver_statuses or []
            solver_status = st.selectbox("Solver status", [any_label] + sorted(statuses), index=0)
        with row1[3]:
            warehouse_id = st.text_input("Warehouse id", value="", placeholder="e.g. WH-0001")

        row2 = st.columns(4)
        with row2[0]:
            sort_label = st.selectbox("Sort by", list(SORT_OPTIONS.keys()), index=0)
        with row2[1]:
            search = st.text_input("Search", value="", placeholder="Run ID, Scenario, or Optimizer")
        with row2[2]:
            page_size = st.number_input(
                "Rows per page",
                min_value=5,
                max_value=settings.max_page_size,
                value=min(settings.default_page_size, settings.max_page_size),
                step=5,
            )
        with row2[3]:
            page = st.number_input("Page", min_value=1, value=1, step=1)

    sort_by, sort_dir = SORT_OPTIONS[sort_label]

    # Turn "(any)"/blank selections into None so api_client omits those params.
    return {
        "scenario": None if scenario == any_label else scenario,
        "optimizer": None if optimizer == any_label else optimizer,
        "solver_status": None if solver_status == any_label else solver_status,
        "warehouse_id": warehouse_id.strip() or None,
        "search": search.strip() or None,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "page": int(page),
        "page_size": int(page_size),
    }
