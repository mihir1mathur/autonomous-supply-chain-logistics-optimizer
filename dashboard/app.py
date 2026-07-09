"""
============================================================================
STREAMLIT DASHBOARD ENTRY POINT
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE IS
-----------------
  The "front door" of the dashboard - the file Streamlit runs. It sets up
  the page, draws the sidebar (navigation + backend connection status + a small
  config/environment panel), and routes to the selected page's render(client).

HOW TO RUN IT (from the project root)
-------------------------------------
    # 1. start the backend services:
    uvicorn api.main:app --reload
    # 2. start this dashboard:
    streamlit run dashboard/app.py
    # then open the URL Streamlit prints (default http://localhost:8501).

WHY THE sys.path LINE AT THE TOP
--------------------------------
  `streamlit run dashboard/app.py` puts the dashboard/ FOLDER on the import
  path, not the PROJECT ROOT - so `import dashboard.config` would not resolve.
  Adding the project root to sys.path (the same trick the notebooks and
  api/main.py use) makes the `dashboard` package importable however it is
  launched. This must happen BEFORE any `from dashboard...` import.

ARCHITECTURE REMINDER
  This dashboard is a PRESENTATION layer only. It talks to the backend solely
  through dashboard/api_client.py and never calls OR-Tools or the database. If
  the backend is offline, the pages show friendly messages rather than crashing.
============================================================================
"""

import os
import sys

# --- make the project root importable (see the docstring above) ------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st  # noqa: E402  (import after the sys.path fix, on purpose)

from dashboard.api_client import get_client  # noqa: E402
from dashboard.config import get_settings  # noqa: E402
from dashboard.pages import (  # noqa: E402
    agent_decisions,
    optimization_history,
    overview,
    reports,
    scenario_analysis,
    system_health,
)

# The sidebar menu: label -> the page module that renders it. Ordered to match
# the recommended demo flow (Overview first, System Health last).
PAGES = {
    "Overview": overview,
    "Optimization History": optimization_history,
    "Scenario Analysis": scenario_analysis,
    "Agent Decisions": agent_decisions,
    "Reports": reports,
    "System Health": system_health,
}


def _render_sidebar(client) -> str:
    """Draw the sidebar (title, navigation, connection status, config) and return the chosen page."""
    settings = get_settings()

    st.sidebar.title("Supply Chain Optimizer")
    st.sidebar.caption("Operations Analytics Dashboard")

    # --- navigation ---
    choice = st.sidebar.radio("Go to", list(PAGES.keys()), index=0)

    st.sidebar.divider()

    # --- backend connection status (never crashes the app) ---
    st.sidebar.subheader("Backend status")
    if client.is_backend_up():
        st.sidebar.success(f"Connected: {settings.api_base_url}")
    else:
        st.sidebar.error(
            f"Offline: {settings.api_base_url}\n\nStart it with:\n\n"
            "uvicorn api.main:app --reload"
        )

    # --- environment / config panel ---
    st.sidebar.divider()
    st.sidebar.subheader("Configuration")
    st.sidebar.write(
        {
            "api_base_url": settings.api_base_url,
            "timeout_s": settings.request_timeout_seconds,
            "version": settings.app_version,
            "demo_mode": settings.demo_mode,
        }
    )
    st.sidebar.caption(
        "Point the dashboard at a different backend by setting the "
        "DASHBOARD_API_BASE_URL environment variable."
    )

    return choice


def main() -> None:
    """Configure the page, draw the sidebar, and route to the chosen page."""
    settings = get_settings()
    st.set_page_config(
        page_title=settings.app_title,
        page_icon="🚚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # One shared API client for the whole session (cached singleton).
    client = get_client()

    st.title("Supply Chain & Logistics Optimizer")
    st.caption(
        "An end-to-end operations platform — an optimization engine, execution "
        "tracking and KPI analytics, and an autonomous multi-agent decision engine "
        "— presented in a single operations dashboard."
    )

    choice = _render_sidebar(client)

    # Route to the selected page. Any unexpected error is shown, never a crash.
    page = PAGES[choice]
    page.render(client)


# Streamlit runs this script with __name__ == "__main__", so this fires when
# launched via `streamlit run dashboard/app.py`. Importing the module elsewhere
# (e.g. the validation script) does NOT run the app - it only checks that
# everything imports cleanly.
if __name__ == "__main__":
    main()
