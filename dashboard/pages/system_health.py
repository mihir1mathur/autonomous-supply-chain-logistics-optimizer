"""
============================================================================
SYSTEM HEALTH PAGE  (Week 8, Part 13)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PAGE SHOWS
--------------------
  A quick health board for the backend the dashboard depends on:
    * backend liveness (GET /health),
    * optimization API availability (GET /optimization/scenarios),
    * agent API availability (GET /agents/status),
    * the scenario catalog availability + count,
    * the time of the last successful backend request, and
    * a friendly, actionable message if anything is offline.

  It also prints the two commands needed to run the whole system, so a first-time
  viewer can get everything up without leaving the page.

WHY THIS PAGE EXISTS
--------------------
  Observability. The dashboard is only as useful as the backend behind it, so a
  single page that says "is the backend up, and which parts respond?" makes demos
  and debugging painless - and proves the dashboard fails gracefully when the
  backend is down (it reports the outage instead of crashing).
============================================================================
"""

from __future__ import annotations

import streamlit as st

from dashboard.api_client import APIClient, APIError
from dashboard.config import get_settings
from dashboard.utils.formatting import format_datetime

RUN_BACKEND = "uvicorn api.main:app --reload"
RUN_DASHBOARD = "streamlit run dashboard/app.py"


def render(client: APIClient) -> None:
    """Render the System Health page."""
    settings = get_settings()
    st.header("System Health")
    st.caption(f"Checking the backend at **{settings.api_base_url}**.")

    # ---- The health checks (each one is independent and never crashes) ----
    checks = [
        _check("Backend liveness", "GET /health", client.get_health),
        _check("Optimization API", "GET /optimization/scenarios", client.get_scenarios),
        _check("Agent API", "GET /agents/status", client.get_agent_status),
    ]

    ok_count = sum(1 for c in checks if c["ok"])
    if ok_count == len(checks):
        st.success(f"All {len(checks)} backend checks passed. The system is healthy.")
    elif ok_count == 0:
        st.error(
            "The backend appears to be offline. Start it, then refresh this page:\n\n"
            f"    {RUN_BACKEND}"
        )
    else:
        st.warning(f"{ok_count}/{len(checks)} backend checks passed. Some APIs are unavailable.")

    # ---- The per-check board ---------------------------------------------
    for check in checks:
        cols = st.columns([3, 2, 5])
        cols[0].markdown(f"**{check['name']}**")
        cols[1].markdown("✅ OK" if check["ok"] else "❌ Down")
        cols[2].caption(check["detail"])

    # ---- Scenario catalog availability + count ---------------------------
    st.subheader("Scenario catalog")
    try:
        catalog = client.get_scenarios()
        count = catalog.get("count", len(catalog.get("scenarios", [])))
        st.write(f"Available - **{count}** scenarios in the catalog.")
    except APIError as exc:
        st.write(f"Unavailable - {exc.message}")

    # ---- Last successful request time ------------------------------------
    st.subheader("Last successful request")
    if client.last_success_at is not None:
        st.write(format_datetime(client.last_success_at))
    else:
        st.write("No successful backend request yet this session.")

    # ---- How to run everything -------------------------------------------
    st.subheader("How to run the system")
    st.markdown("**1. Start the backend (Weeks 4-7):**")
    st.code(RUN_BACKEND, language="bash")
    st.markdown("**2. Start this dashboard (Week 8):**")
    st.code(RUN_DASHBOARD, language="bash")
    st.caption(
        "The dashboard is a presentation layer: it reads and writes only through "
        "these backend APIs. If the backend is down, every page shows a friendly "
        "message instead of crashing."
    )


def _check(name: str, endpoint: str, call) -> dict:
    """
    Run one health call and return a small result dict {name, ok, detail}.

    Never raises: an APIError becomes ok=False with the friendly message, so the
    health board itself is immune to the very outages it reports.
    """
    try:
        call()
        return {"name": name, "ok": True, "detail": f"{endpoint} responded."}
    except APIError as exc:
        return {"name": name, "ok": False, "detail": exc.message}
