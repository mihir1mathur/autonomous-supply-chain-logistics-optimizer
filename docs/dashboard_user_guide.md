# Dashboard User Guide (Week 8)

_A short, practical guide to running and using the Streamlit analytics
dashboard for the Supply Chain & Logistics Optimizer._

## 1. Start the backend

The dashboard shows what the backend produces, so start the backend first
(Weeks 4–7). From the project root:

```bash
pip install -r requirements.txt          # includes streamlit + plotly (Week 8)
python database/init_db.py                # (if not already) create tables
python notebooks/week3_load_database.py   # (if not already) load the data
uvicorn api.main:app --reload             # start the API at http://127.0.0.1:8000
```

You can confirm it is up by opening <http://127.0.0.1:8000/docs>.

## 2. Start the dashboard

In a second terminal, from the project root:

```bash
streamlit run dashboard/app.py
```

Streamlit prints a local URL (default <http://localhost:8501>). Open it in a
browser.

> If the backend is **not** running, the dashboard still opens — the sidebar
> shows an **Offline** badge and each page shows a friendly message. Start the
> backend and refresh.

**Pointing at a different backend:** set one environment variable before
launching (no code change):

```bash
# macOS/Linux
export DASHBOARD_API_BASE_URL=http://my-backend:8000
# Windows (PowerShell)
$env:DASHBOARD_API_BASE_URL = "http://my-backend:8000"
```

## 3. What each page does

The sidebar lets you switch pages. It also shows the **backend connection
status** and the current **configuration** (base URL, timeout, version).

| Page | What it shows | Key actions |
|------|----------------|-------------|
| **Overview** | Aggregate KPIs (stored runs, cost, distance, utilization, orders, stockouts, runtime), runs per scenario/optimizer, trends, and the architecture + five-agent flow. | Read the headline numbers. |
| **Optimization History** | A filter/sort/paginated table of every stored run; drill into one run for its KPIs, before/after evaluation, and scenario changes. | Filter, sort, pick a run, copy its `run_id`, export CSV / JSON. |
| **Scenario Analysis** | The scenario catalog with descriptions, and charts comparing stored runs across scenarios. | Compare scenarios; **Simulate** a scenario (a what-if that is *not* stored). |
| **Agent Decisions** | The key page: type a plain-English goal and let the five-agent crew plan, run, judge and explain. | **Decide** (store the run) or **Simulate** (what-if); read the plan, verdict, trace and report; export the report. |
| **Reports** | The latest agent report in Markdown / Text / JSON, with recommendations. | View and download the report; generate one if none exists yet. |
| **System Health** | Backend liveness and per-API availability, the scenario count, and the last successful request time. | Diagnose an offline backend; copy the run commands. |

## 4. How to run an agent decision

1. Open **Agent Decisions**.
2. In the text box, describe what you want, e.g.
   *"Optimize deliveries for a holiday rush and reduce late deliveries."*
3. (Optional) Expand **Optional overrides** to pin an optimizer, scenario,
   priority, warehouse, or shipment cap. Leave them blank to let the agents
   infer everything from your text.
4. Click **Decide** (stores the optimization run) or **Simulate** (a what-if
   that is not stored).
5. Read the result:
   - **Planner output** — which optimizer/priority it chose and why.
   - **Scenario selected** — which existing scenario it matched.
   - **Optimization outcome** — the stored `run_id` (or "simulated").
   - **Evaluation verdict** — improved / degraded / mixed / neutral, with KPIs
     and an improvement chart.
   - **Execution trace** — Planner → Scenario → Optimization → Evaluation →
     Reporting, each step timed and marked OK/failed (the workflow is
     **auditable**).
   - **Report** — Markdown | Text | JSON tabs, plus recommendations.
6. Use the **Download** buttons to export the report as Markdown or JSON.

## 5. How to interpret the KPIs

- **Total cost** — the plan's total (simulated) cost; lower is better.
- **Travel distance (km)** — total road distance (straight-line × a winding
  factor); lower is better.
- **Vehicle / warehouse utilization** — how much capacity is used, shown as a
  **percentage** (the backend stores it as a 0–1 fraction; the dashboard always
  displays it as `%`). Higher usually means less waste, but very close to 100%
  can signal strain.
- **Orders fulfilled** — shipments the plan serves; higher is better.
- **Stockouts** — demands that could not be met from stock; lower is better.
- **Late deliveries** — shipments flagged at risk of being late (a documented
  proxy based on how heavily a vehicle is loaded); lower is better.
- **Runtime** — how long the solver took.
- **Improvement percentages** (evaluation) — the optimized plan compared to a
  naive baseline; a **positive** value is an improvement.

The KPIs are computed by the backend (Week 6). The dashboard only formats and
charts them.

## 6. How to export results

- **Optimization History → Download history (CSV)** — the current page of runs
  as a spreadsheet-friendly CSV.
- **History run drill-down → Download run (JSON)** — one stored run in full.
- **Agent Decisions / Reports → Download report (Markdown / JSON)** — the agent
  report the Reporting Agent produced.

All exports are the data the backend produced — the dashboard never invents
numbers to export.

## 7. Troubleshooting

- **Sidebar says "Offline".** The backend is not reachable. Start it with
  `uvicorn api.main:app --reload`, or set `DASHBOARD_API_BASE_URL` to the right
  address, then refresh.
- **A page says "No stored runs yet".** Store some runs first — use
  **Agent Decisions → Decide**, or `POST /optimization/run` on the backend.
- **An agent decision shows `success = false`.** That is by design: the trace
  shows exactly which step failed (e.g. an unknown warehouse). Fix the input and
  try again.
- **Verify everything with one command:**
  `python notebooks/week8_validation.py` (prints a PASS/FAIL checklist).
