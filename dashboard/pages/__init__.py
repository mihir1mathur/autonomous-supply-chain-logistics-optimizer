"""
============================================================================
DASHBOARD PAGES  (Week 8)   -- one file per page
Project: Supply Chain & Logistics Optimizer
============================================================================

Each module here is ONE page of the dashboard and exposes a single entry point:

        def render(client: APIClient) -> None

app.py picks a page from the sidebar and calls its render(client). A page reads
data through the shared api_client, formats it with utils.formatting, and lays
it out with the reusable components. Pages never talk to the backend directly
(only via the client) and never compute a KPI (only via the API).

  overview.py             the at-a-glance summary + architecture
  optimization_history.py  browse/filter stored runs + drill into one
  scenario_analysis.py     scenario catalog + comparisons + optional simulate
  agent_decisions.py       run the Week 7 crew from plain English
  reports.py               view the agent report (markdown/text/json)
  system_health.py         backend + API availability
============================================================================
"""
