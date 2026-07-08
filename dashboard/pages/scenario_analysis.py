"""
============================================================================
SCENARIO ANALYSIS PAGE  (Week 8, Part 8)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  * The scenario catalog (GET /optimization/scenarios) with descriptions.
  * A comparison of the STORED runs grouped by scenario - cost, distance,
    vehicle utilization, orders fulfilled and stockouts per scenario - drawn
    from the optimization history.
  * An optional "simulate" panel: run a chosen scenario as a WHAT-IF via
    POST /optimization/simulate. A simulate is NOT stored (the history is
    unchanged); only choosing "run" on the History/Agents flow persists a run.

WHY SIMULATE (NOT RUN) HERE
---------------------------
  This page is for exploring "what would this scenario look like?" without
  polluting the stored history. That maps exactly to the Week 6 /simulate
  endpoint, which the Week 8 prompt says to use here. The button is explicit
  about not persisting.
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.components.charts import (
    cost_by_scenario,
    distance_by_scenario,
    limit_rows,
    orders_by_scenario,
    stockouts_by_scenario,
    utilization_by_scenario,
)
from dashboard.components.filters import OPTIMIZERS
from dashboard.components.kpi_cards import run_kpi_cards
from dashboard.components.tables import history_to_dataframe, render_scenario_table


def render(client: APIClient) -> None:
    """Render the Scenario Analysis page."""
    st.header("Scenario Analysis")
    st.caption(
        "The 'what if' conditions the optimizer can face, and how the stored runs "
        "compare across them. Scenarios only change the optimizer's INPUTS - the "
        "same Week 5 solvers run underneath."
    )

    # ---- The scenario catalog --------------------------------------------
    st.subheader("Scenario catalog")
    scenarios = []
    try:
        catalog = client.get_scenarios()
        scenarios = catalog.get("scenarios", [])
        render_scenario_table(scenarios)
    except APIError as exc:
        st.error(f"Could not load the scenario catalog. {exc.message}")

    # ---- Comparison of stored runs by scenario ---------------------------
    st.subheader("Stored runs compared by scenario")
    try:
        page = client.get_history(page=1, page_size=client.settings.max_page_size,
                                  sort_by="created_at", sort_dir="desc")
        df = limit_rows(history_to_dataframe(page.get("items", [])))
    except APIError as exc:
        st.error(f"Could not load the history for comparison. {exc.message}")
        df = None

    if df is not None and not df.empty:
        row1 = st.columns(2)
        with row1[0]:
            cost_by_scenario(df)
        with row1[1]:
            distance_by_scenario(df)
        row2 = st.columns(2)
        with row2[0]:
            utilization_by_scenario(df)
        with row2[1]:
            orders_by_scenario(df)
        stockouts_by_scenario(df)
    else:
        st.info("No stored runs yet to compare. Run some optimizations first.")

    # ---- Optional: simulate a scenario (a what-if, NOT stored) ------------
    st.subheader("Simulate a scenario (what-if, not stored)")
    _render_simulate_panel(client, scenarios)


def _render_simulate_panel(client: APIClient, scenarios: list[dict]) -> None:
    """A small form to run one scenario as a non-persisted what-if."""
    scenario_keys = [s.get("key") for s in scenarios if s.get("key")] or ["normal"]

    with st.form("simulate_scenario_form"):
        cols = st.columns(3)
        with cols[0]:
            scenario = st.selectbox("Scenario", scenario_keys, index=0)
        with cols[1]:
            optimizer = st.selectbox("Optimizer", OPTIMIZERS, index=0)
        with cols[2]:
            max_shipments = st.number_input("Max shipments", min_value=1, value=40, step=5)
        submitted = st.form_submit_button("Simulate (does not store a run)")

    if not submitted:
        return

    payload = {"scenario": scenario, "optimizer": optimizer,
               "max_shipments": int(max_shipments), "evaluate": True}
    try:
        with st.spinner("Simulating (this runs a real optimization, but does not store it)..."):
            result = client.simulate_optimization(payload)
    except APIError as exc:
        st.error(f"Simulation failed. {exc.message}")
        return

    persisted = result.get("persisted", False)
    st.success(
        f"Simulated '{result.get('scenario_name', scenario)}' with the "
        f"{optimizer} optimizer. Stored: {'yes' if persisted else 'no (what-if only)'}."
    )
    run_kpi_cards(result.get("metrics", {}))

    changes = result.get("scenario_changes") or []
    if changes:
        st.markdown("**Scenario changes applied**")
        for change in changes:
            st.markdown(f"- {change}")
