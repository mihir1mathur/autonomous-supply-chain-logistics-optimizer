# Dashboard Architecture (Week 8)

_Supply Chain & Logistics Optimizer — the analytics & visualization layer._

## Why Week 8 exists

Weeks 4–7 built a capable backend: a REST API (Week 4) over a PostgreSQL
database (Week 3), an OR-Tools optimization engine (Week 5), an execution layer
that runs optimizations, measures twelve KPIs, evaluates before-vs-after and
stores every run (Week 6), and an AI multi-agent orchestration layer that turns
a plain-English request into a recorded, explained decision (Week 7).

All of that spoke **JSON**. It was correct and complete, but it was only
demonstrable through Swagger, `curl`, or the test scripts. Week 8 adds a
**Streamlit dashboard** that makes the existing system *visible*: it charts the
optimization history and KPIs, lets a user drive the agents from plain English,
draws the auditable five-agent execution trace, and renders the agent reports —
turning "backend + optimization + agents" into an **end-to-end, visible
operations platform**.

Week 8 is **100% additive**: it adds a new `dashboard/` package and three docs;
it rewrites nothing in Weeks 0–7 and changes no backend behavior.

## The one architectural rule

> **The dashboard is a presentation layer only.**

It talks to the backend **only** over HTTP, through a single client module, and
it **never**:

- calls OR-Tools directly,
- accesses the SQLAlchemy models or the database,
- duplicates the execution service, the KPI calculations, or the evaluation
  logic.

Every number it shows is produced by the backend and merely **formatted** and
**arranged** for the eye.

### Correct flow

```
Streamlit Dashboard
    -> FastAPI APIs
    -> Week 6 Execution Service / Week 7 Agent Service
    -> Week 5 Optimizers
    -> PostgreSQL
```

### Incorrect flow (deliberately impossible here)

```
Streamlit Dashboard
    -> OR-Tools directly          (NEVER)
    -> SQLAlchemy / PostgreSQL    (NEVER)
```

## How it connects to FastAPI

There is exactly **one seam** between the UI and the backend:
`dashboard/api_client.py`. Every page and component goes through it; none of
them build URLs or make HTTP calls themselves. This mirrors the Week 7 "one tool
seam" idea — a single door to the platform makes the rule *"the dashboard never
bypasses the backend"* easy to see and impossible to break by accident.

The client:

- reads **one** base URL from `dashboard/config.py`
  (`DASHBOARD_API_BASE_URL`, default `http://127.0.0.1:8000`), so pointing the
  dashboard at a different backend is a single environment variable — no code
  change;
- exposes **one method per endpoint** (see the table below);
- converts any transport problem (backend offline, timeout, HTTP error) into a
  small, friendly `APIError` carrying a human-readable message, so a page only
  ever has to catch one exception type;
- remembers the time of the last successful request (shown on System Health).

## Why it does not call OR-Tools directly

Three reasons, all about keeping the system trustworthy and maintainable:

1. **Single source of truth for the numbers.** The twelve KPIs and the
   before/after evaluation are computed once, by the Week 6 `metrics.py` /
   `evaluation.py` code. If the dashboard recomputed them, the two could drift
   and a viewer would not know which to believe. The dashboard shows exactly the
   stored/served numbers.
2. **No duplicated logic.** OR-Tools calls, scenario transforms, and DB access
   already live behind the API. Re-implementing any of that in the UI would be
   duplication that rots.
3. **Clean separation of concerns.** A presentation layer that only consumes
   APIs can be replaced, redeployed, or pointed at a remote backend without
   touching the engine — the hallmark of a layered system.

## Pages and components

Small, modular files — never one giant dashboard file.

```
dashboard/
├── app.py            Streamlit entry point (sidebar + connection status + routing)
├── config.py         settings (API base URL, timeout, page/chart limits, demo flag)
├── api_client.py     THE only seam to FastAPI (one method per endpoint, APIError)
├── components/       reusable UI pieces
│   ├── kpi_cards.py     metric cards (utilization shown as %, not 0..1)
│   ├── charts.py        Plotly charts over API data (visualize, never compute)
│   ├── tables.py        history + scenario tables (and the shared dataframe builder)
│   ├── filters.py       history filter / sort / paging controls (backend does the work)
│   ├── agent_trace.py   the five-agent execution trace (flow + table + errors)
│   └── report_viewer.py the agent report as Markdown | Text | JSON tabs
├── pages/            one file per page, each exposing render(client)
│   ├── overview.py             KPIs + activity breakdown + trends + architecture
│   ├── optimization_history.py browse/filter runs + drill into one
│   ├── scenario_analysis.py    scenario catalog + comparisons + optional simulate
│   ├── agent_decisions.py      run the crew from plain English (key page)
│   ├── reports.py              view/download the agent report
│   └── system_health.py        backend + API availability
└── utils/
    ├── formatting.py  pure display helpers (%, money, ms, dates) — no Streamlit
    └── export.py      CSV / JSON / Markdown download builders + buttons
```

Each page reads data through the client, formats it with `utils.formatting`, and
lays it out with the reusable components. A page never talks to the backend
directly and never computes a KPI.

## API endpoints consumed

| Method & path                     | Week | Used by (pages)                                   |
|-----------------------------------|------|---------------------------------------------------|
| `GET /health`                     | 4    | sidebar status, System Health                     |
| `GET /optimization/scenarios`     | 6    | Scenario Analysis, History (filters), Agents      |
| `GET /optimization/metrics`       | 6    | Overview                                          |
| `GET /optimization/history`       | 6    | History, Overview, Scenario Analysis              |
| `GET /optimization/{run_id}`      | 6    | History (drill-down)                              |
| `POST /optimization/run`          | 6    | (available in client; History/Scenario "run")     |
| `POST /optimization/simulate`     | 6    | Scenario Analysis (what-if)                       |
| `POST /agents/decide`             | 7    | Agent Decisions (store the run)                   |
| `POST /agents/simulate`           | 7    | Agent Decisions, Reports (what-if)                |
| `GET /agents/status`              | 7    | System Health, Overview                           |

The dashboard adds **no new endpoints** — it consumes the existing Week 6 and
Week 7 APIs.

## Error handling

Resilience is a first-class feature: **if the backend is down, the dashboard
shows a friendly message instead of crashing.**

- `api_client._request()` is the single choke point that turns
  `httpx.ConnectError` / `TimeoutException` / HTTP 4xx–5xx into an `APIError`
  with an actionable message (e.g. *"Cannot reach the backend … start it with
  `uvicorn api.main:app --reload`"*).
- The sidebar shows a live **Connected / Offline** badge without ever raising.
- Every page wraps its calls in `try / except APIError` and renders `st.error`
  / `st.info` with the message.
- The `/agents/decide` contract (200 even on a partial failure, with `success`
  and a `trace`) is honored: a failed decision shows `success=false` and the
  failing step is highlighted in the trace — it fails **loudly**, not silently.

## Future deployment path

The dashboard is deployment-ready by construction. Because the only coupling to
the backend is one URL from an environment variable:

- **Local:** run the API with `uvicorn` and the dashboard with `streamlit run`.
- **Containers:** package the API and the dashboard as two images; set
  `DASHBOARD_API_BASE_URL` to the API service address (Docker Compose / ECS).
- **Cloud (AWS sketch):** the API on ECS/Fargate behind a load balancer against
  an RDS PostgreSQL; the Streamlit dashboard on ECS/Fargate (or App Runner) with
  `DASHBOARD_API_BASE_URL` pointed at the API's URL. No dashboard code changes —
  only configuration. Secrets (any LLM key for the Week 7 crewai mode) stay on
  the **backend**, never in the dashboard.

This is described honestly as a **professional project dashboard / analytics
layer**, not a hardened enterprise product — but the separation of concerns is
exactly what makes hardening it later a configuration exercise, not a rewrite.
