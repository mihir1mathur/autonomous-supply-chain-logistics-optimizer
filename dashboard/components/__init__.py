"""
============================================================================
DASHBOARD COMPONENTS   -- reusable UI pieces
Project: Supply Chain & Logistics Optimizer
============================================================================

Small, self-contained Streamlit widgets that the pages compose together. Each
component does ONE visual job and takes plain API data in; none of them talk to
the backend (that is api_client's job) and none of them compute a KPI (that is
the backend's job). Keeping the UI in small reusable pieces is why there is no
one giant dashboard file.

  kpi_cards.py    metric "cards" (a big number + label), e.g. run count, cost
  charts.py       Plotly charts over API data (cost/distance/utilization/...)
  tables.py       clean dataframes for history and catalogs
  filters.py      sidebar/inline filter + sort controls
  agent_trace.py  the five-agent execution trace (timeline / table)
  report_viewer.py  the agent report shown as Markdown | Text | JSON tabs
============================================================================
"""
