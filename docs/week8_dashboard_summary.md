# Week 8 — Dashboard Summary

_What Week 8 added to the Supply Chain & Logistics Optimizer, and how it fits._

## What was added

Week 8 adds a **Streamlit analytics dashboard** that makes the existing backend
visible and demo-ready. It is a **presentation layer only**: it consumes the
existing Week 6 `/optimization/*` and Week 7 `/agents/*` endpoints over HTTP and
never calls OR-Tools, the database, or the services directly. It computes no
KPIs — it formats and charts the numbers the backend already produced.

Highlights:

- A six-page dashboard (Overview, Optimization History, Scenario Analysis,
  Agent Decisions, Reports, System Health) with sidebar navigation and a live
  backend connection badge.
- **KPI cards** that read the Week 6 aggregate metrics and single-run metrics
  (utilization shown as a percentage, never as a raw 0–1 value).
- **Charts** (Plotly) for cost, distance, utilization, orders and stockouts by
  scenario, runtime by optimizer, runs over time, and per-run improvement.
- An **optimization history explorer** with backend-driven filter/sort/paging
  and a per-run drill-down (KPIs, before/after evaluation, scenario changes).
- **Scenario comparison** across the stored runs, plus an optional what-if
  **simulate**.
- An **Agent Decisions** page that turns a plain-English request into a recorded,
  explained decision via the Week 7 crew.
- An **execution-trace viewer** that draws the five-agent flow (Planner →
  Scenario → Optimization → Evaluation → Reporting), each step timed and
  pass/fail — proof that the autonomous workflow is auditable.
- A **report viewer** (Markdown | Text | JSON tabs) that renders the Week 7
  Reporting Agent output (it never writes a report itself).
- **Exports**: history CSV, run JSON, report Markdown/JSON — via Streamlit
  download buttons.
- **Resilience**: if the backend is offline, every page shows a friendly message
  instead of crashing.

## Files created

**Dashboard package** (`dashboard/`)

- `__init__.py`, `app.py`, `config.py`, `api_client.py`
- `components/`: `__init__.py`, `kpi_cards.py`, `charts.py`, `tables.py`,
  `filters.py`, `agent_trace.py`, `report_viewer.py`
- `pages/`: `__init__.py`, `overview.py`, `optimization_history.py`,
  `scenario_analysis.py`, `agent_decisions.py`, `reports.py`, `system_health.py`
- `utils/`: `__init__.py`, `formatting.py`, `export.py`

**Scripts** (`notebooks/`)

- `week8_dashboard_demo.py` — a printed walkthrough + live endpoint checks.
- `week8_validation.py` — a PASS/FAIL checklist for the dashboard.

**Documentation** (`docs/`)

- `dashboard_architecture.md` — why Week 8 exists, the architecture, endpoints,
  error handling, and the deployment path.
- `dashboard_user_guide.md` — how to run and use every page.
- `week8_dashboard_summary.md` — this file.

**Notes** (`notes/Week8/`)

- `00_INDEX.txt` plus `01`–`12` learning notes (same 12-section style as
  Weeks 0–7).

## Files modified (additively)

- `requirements.txt` — added `streamlit` and `plotly` (the only two new
  dependencies; `httpx` and `pandas` were already present and are reused).
- `.env.example` — added the optional `DASHBOARD_*` settings.
- `README.md` — added the Week 8 section and updated the project structure.

No Week 0–7 code file was rewritten. No backend behavior changed.

## How Week 8 connects to Weeks 0–7

```
Week 0-2  understand + clean + simulate the logistics data
Week 3    store it in PostgreSQL behind SQLAlchemy
Week 4    serve it via a FastAPI REST API
Week 5    optimize it with OR-Tools (/optimize)
Week 6    run + measure (12 KPIs) + evaluate + store runs (/optimization)
Week 7    let agents decide + explain (/agents)
Week 8    VISUALIZE all of it in a dashboard  <-- consumes Week 6 + Week 7 APIs
```

The dashboard sits at the very top of the stack and reaches the lower layers
**only through the API**:

```
Dashboard -> FastAPI -> Execution Service / Agent Service -> Optimizers -> PostgreSQL
```

## Software-engineering relevance

Week 8 demonstrates skills that matter for backend / full-stack engineering,
described honestly for a professional project dashboard (not an enterprise
product):

- **API consumption** — a typed client with one method per endpoint.
- **Clean frontend/backend separation** — the UI never bypasses the services.
- **Reusable client layer** — a single seam to the backend (one base URL, one
  error type).
- **Modular components** — small, single-purpose UI pieces; no giant file.
- **Error handling / resilience** — the dashboard degrades gracefully when the
  backend is down.
- **Data visualization** — charts and KPI cards over real API data.
- **Observability** — a System Health page and a live connection badge.
- **Debugging** — the auditable agent trace makes an autonomous run inspectable.
- **User-facing system design** — a guided flow a non-author can follow.
- **Maintainability** — configuration over hard-coding; no duplicated logic.

## The one-line pitch

> _"Week 8 made the system demonstrable. Instead of only returning JSON from
> APIs, I built a Streamlit analytics dashboard that visualizes optimization
> history, KPIs, scenario comparisons, agent decisions, execution traces, and
> reports. The dashboard remains a presentation layer only; it consumes the
> existing FastAPI endpoints and never bypasses the execution service."_

## Next recommended step

**Week 9 — deployment (Docker + AWS)** and/or **testing / production
hardening**: containerize the API and the dashboard, point
`DASHBOARD_API_BASE_URL` at a deployed backend (ECS/Fargate + RDS), and add a
test suite and CI. The layering built through Weeks 3–8 makes this a
configuration exercise, not a rewrite.
