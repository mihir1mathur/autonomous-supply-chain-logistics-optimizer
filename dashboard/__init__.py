"""
============================================================================
DASHBOARD PACKAGE   -- the Streamlit analytics / visualization layer
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS PACKAGE IS
--------------------
  The PRESENTATION layer. A Streamlit dashboard that makes the existing
  backend visible and demonstrable: it charts the optimization history and KPIs
  from the execution layer, lets a user drive the autonomous multi-agent
  decision engine and read its decisions, and shows whether the system is
  healthy - all by CONSUMING the existing FastAPI endpoints over HTTP.

THE ONE RULE OF THIS PACKAGE
----------------------------
  The dashboard is a presentation layer ONLY. It NEVER calls OR-Tools, NEVER
  touches the SQLAlchemy models, and NEVER recomputes a KPI. Every number it
  shows comes from an API response. The single place allowed to talk to the
  backend is dashboard/api_client.py. If the backend is offline, the dashboard
  shows a friendly message instead of crashing.

LAYOUT (small, modular files - never one giant dashboard)
---------------------------------------------------------
  app.py           the Streamlit entry point (sidebar + page routing)
  config.py        settings (API base URL, timeouts, page/chart limits)
  api_client.py    the ONLY seam to FastAPI (one method per endpoint)
  components/      reusable UI pieces (kpi cards, charts, tables, filters,
                   agent trace, report viewer)
  pages/           one file per page (overview, history, scenarios, agents,
                   reports, system health)
  utils/           formatting + export helpers (no Streamlit, no backend)

RUN IT
------
    uvicorn api.main:app --reload      # start the backend services
    streamlit run dashboard/app.py     # start this dashboard
============================================================================
"""
