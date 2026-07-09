"""
============================================================================
SCENARIO ANALYSIS PAGE
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
  polluting the stored history. That maps exactly to the execution layer's
  /simulate endpoint, which is used here. The button is explicit
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
from dashboard.utils.formatting import humanize_scenario_change


# ---------------------------------------------------------------------------
# DISPLAY-ONLY wording (presentation layer). The backend scenario catalog,
# multipliers, and API responses are unchanged; these maps and helpers only
# polish the names, descriptions, and "applied changes" lines shown on screen.
# ---------------------------------------------------------------------------
_SCENARIO_DISPLAY_NAMES = {
    "normal": "Normal Operations",
    "high_demand": "High Demand",
    "low_demand": "Low Demand",
    "vehicle_breakdown": "Vehicle Breakdown",
    "warehouse_closed": "Warehouse Closure",
    "fuel_price_increase": "Fuel Price Increase",
    "supplier_delay": "Supplier Delay",
    "priority_orders": "Priority Orders",
    "holiday": "Holiday Peak",
    "demand_spike": "Demand Spike",
    "vehicle_failure": "Vehicle Failure",
}

_SCENARIO_DISPLAY_DESCRIPTIONS = {
    "normal": "Business as usual with the baseline operational configuration.",
    "high_demand": "Customer demand is increased by 80%, placing additional pressure on fleet capacity.",
    "low_demand": "Customer demand is reduced by 50%, leaving spare fleet capacity.",
    "vehicle_breakdown": "Half of the fleet is unavailable; the remaining vehicles must absorb the workload.",
    "warehouse_closed": "One operating warehouse is closed and its local fleet is reduced by half.",
    "fuel_price_increase": "Per-kilometer fuel costs increase by 50%, raising the cost of the same plan.",
    "supplier_delay": "A supplier ships late: tracked inventory falls to 40% while demand rises 20%, pushing more orders to pending.",
    "priority_orders": "Only the highest-priority half of orders are served - triage under constrained capacity.",
    "holiday": "A holiday peak combining 60% higher demand, 20% of the fleet unavailable, and 10% higher fuel costs.",
    "demand_spike": "A sudden surge increases demand by 150%, well beyond normal capacity.",
    "vehicle_failure": "A major fleet failure leaves only half of the vehicles available.",
}


def _polish_category(category) -> str:
    """Title-case a category label for display (e.g. 'high_demand' -> 'High Demand')."""
    if not category:
        return category
    return str(category).replace("_", " ").title()


def _polish_scenarios(scenarios: list[dict]) -> list[dict]:
    """Return display copies with polished names/descriptions (originals untouched)."""
    polished = []
    for s in scenarios:
        key = s.get("key")
        polished.append(
            {
                **s,
                "name": _SCENARIO_DISPLAY_NAMES.get(key, s.get("name")),
                "category": _polish_category(s.get("category")),
                "description": _SCENARIO_DISPLAY_DESCRIPTIONS.get(key, s.get("description")),
            }
        )
    return polished


def render(client: APIClient) -> None:
    """Render the Scenario Analysis page."""
    st.header("Scenario Analysis")
    st.caption(
        "The 'what-if' conditions the optimizer can face, and how the stored runs "
        "compare across them. Each scenario modifies demand, resource, or cost "
        "assumptions while the same optimization engine solves every scenario."
    )

    # ---- The scenario catalog --------------------------------------------
    st.subheader("Business Scenarios")
    scenarios = []
    try:
        catalog = client.get_scenarios()
        scenarios = catalog.get("scenarios", [])
        render_scenario_table(_polish_scenarios(scenarios))
    except APIError as exc:
        st.error(f"Could not load the scenario catalog. {exc.message}")

    # ---- Comparison of stored runs by scenario ---------------------------
    st.subheader("Stored Runs Compared by Scenario")
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
    st.subheader("Simulate a Scenario (What-If, Not Stored)")
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
            max_shipments = st.number_input("Max Shipments", min_value=1, value=40, step=5)
        submitted = st.form_submit_button("Run What-If Simulation")

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

    st.success(
        "Simulation completed successfully. Results are temporary and have not "
        "been saved to optimization history."
    )
    run_kpi_cards(result.get("metrics", {}))

    changes = result.get("scenario_changes") or []
    if changes:
        st.markdown("**Applied Scenario Changes**")
        for change in changes:
            st.markdown(f"- {humanize_scenario_change(change)}")
