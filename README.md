# 🚚 Autonomous Supply Chain & Logistics Optimizer

> **An end-to-end AI-powered Supply Chain Optimization Platform built with FastAPI, PostgreSQL, OR-Tools, CrewAI, Streamlit, and designed for AWS deployment.**

<p align="center">

**FastAPI • PostgreSQL • Google OR-Tools • CrewAI • Streamlit • SQLAlchemy • Docker • AWS**

<p align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-red) ![Google OR-Tools](https://img.shields.io/badge/Google_OR--Tools-orange) ![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-purple) ![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit) ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker) ![AWS Ready](https://img.shields.io/badge/AWS-Deployment_Ready-FF9900?logo=amazonaws)


</p>

<p align="center">

Building intelligent, scalable, and autonomous supply chain systems using modern AI and optimization techniques.

</p>

---

## Overview

This project transforms a real-world e-commerce dataset into an intelligent logistics optimization platform capable of:

- 📦 Warehouse Selection
- 🚚 Vehicle Assignment
- 🛣 Route Optimization
- 📈 KPI Benchmarking
- 🤖 Autonomous Multi-Agent Decision Making
- 📊 Interactive Analytics Dashboard
- ☁️ AWS Deployment 

The platform is developed incrementally over multiple engineering milestones, progressing from raw dataset analysis to an autonomous AI-powered logistics optimization system.

---

## Dataset

**Brazilian E-Commerce Public Dataset by Olist** — roughly 100,000 real,
anonymized orders placed between 2016 and 2018, including customers, sellers,
products, payments, reviews, delivery timestamps, and geographic coordinates.

See the documentation for full details:

- [`docs/dataset_overview.md`](docs/dataset_overview.md) — every file, its
  columns, how the tables connect, and the supply chain mapping.
- [`docs/logistics_data_model.md`](docs/logistics_data_model.md) — how the
  e-commerce data is reinterpreted as a logistics dataset, with explicit
  modeling assumptions.
- [`docs/future_database_design.md`](docs/future_database_design.md) — the
  planned database tables, columns, and relationships (design only, no SQL).

## Planned Features

- **Delivery delay analysis** — measure on-time vs. late deliveries.
- **Distance & route estimation** — use geolocation to estimate travel.
- **Disruption simulation** — inventory shortages, traffic, weather, congestion.
- **Route optimization** — minimize distance, time, and cost.
- **Inventory & warehouse modeling** — stock levels and fulfillment decisions.
- **Backend API** — serve data and optimization results.
- **Interactive dashboard** — visualize routes, delays, and KPIs.
- **Autonomous planning** — automated decision-making and replanning.

## Planned Tech Stack

| Layer | Technology |
|-------|-----------|
| Core language | Python |
| Backend API | FastAPI |
| Database | PostgreSQL |
| Caching / queues | Redis |
| Optimization | OR-Tools |
| Agents / autonomous planning | CrewAI |
| Dashboard | Streamlit |
| Containerization | Docker |
| Cloud | AWS |

> The tech stack above is the **target** for the full project. It is being
> introduced gradually; early weeks focus on understanding and analysis.

## Project Structure

```
Supply Chain Logistics Optimizer/
├── README.md                         # This file
├── data/                             # Raw Olist CSV files (unchanged)
├── processed/                        # Cleaned + joined data (generated)
├── simulation/                       # Simulated logistics datasets (generated)
│   ├── warehouses.csv                # Sellers remapped as fulfillment origins
│   ├── inventory.csv                 # Simulated stock per warehouse
│   ├── vehicles.csv                  # Simulated delivery fleet
│   ├── disruptions.csv               # Simulated traffic/weather/etc. events
│   └── delivery_routes.csv           # Estimated warehouse → customer routes
├── .env.example                      # Template for local database settings
├── database/                         # Database layer (Week 3)
│   ├── config.py                     # Reads settings from .env, builds DB URL
│   ├── connection.py                 # SQLAlchemy engine, session, Base
│   ├── init_db.py                    # Creates all tables/indexes/FKs
│   └── crud.py                       # Reusable read/write query functions
├── models/                           # SQLAlchemy ORM models (Week 3)
│   ├── customer.py                   # customers        (real)
│   ├── seller.py                     # sellers          (real)
│   ├── product.py                    # products         (real)
│   ├── order.py                      # orders           (real)
│   ├── warehouse.py                  # warehouses       (real + simulated ops)
│   ├── inventory.py                  # inventory        (simulated)
│   ├── vehicle.py                    # vehicles         (simulated)
│   ├── route.py                      # delivery_routes  (real ids + computed)
│   ├── disruption.py                 # disruptions      (simulated)
│   └── optimization_run.py           # optimization_runs (Week 6, stored runs)
├── api/                              # FastAPI backend (Week 4)
│   ├── main.py                       # Creates the app, wires routers + errors
│   ├── config.py                     # API settings (title, page sizes, CORS)
│   ├── database.py                   # Reuses Week 3 engine; get_db per request
│   ├── dependencies.py               # Shared injectables (db, pagination, search)
│   ├── schemas/                      # Pydantic schemas (7 entities + optimization + execution + agent)
│   ├── routers/                      # REST endpoints, thin (7 entities + /optimize + /optimization + /agents)
│   ├── services/                     # Business logic (7 entities + optimization + execution + agent)
│   └── utils/                        # Errors + handlers, pagination, validation
├── optimization/                     # Optimization engine (Week 5) + execution (Week 6)
│   ├── config.py                     # Tunable settings (OPT_*): time limit, caps
│   ├── utils.py                      # Haversine distance, Timer, simulated demand
│   ├── cost_functions.py             # How a plan is priced (cost, unused capacity)
│   ├── constraints.py                # Rules a plan must obey (capacity, inventory)
│   ├── solution_models.py            # Input/output dataclasses the solvers speak
│   ├── assignment_solver.py          # Shipment -> vehicle assignment (CP-SAT)
│   ├── warehouse_selector.py         # Nearest in-stock warehouse (greedy)
│   ├── vehicle_optimizer.py          # Fleet load balancing (CP-SAT)
│   ├── route_optimizer.py            # Nearest-neighbour routing (VRP-ready)
│   ├── execution_config.py           # (Week 6) KPI pricing / threshold tunables
│   ├── metrics.py                    # (Week 6) the 12 KPIs of a run (pure)
│   ├── evaluation.py                 # (Week 6) before/after + naive baselines (pure)
│   └── scenarios.py                  # (Week 6) the "what if" catalog + transforms
├── agents/                           # AI multi-agent orchestration layer (Week 7)
│   ├── config.py                     # AGENT_* settings + orchestration-mode detection
│   ├── utils.py                      # Logging/timing/tracing + structured contracts
│   ├── prompts.py                    # Each agent's role/goal/backstory + task templates
│   ├── base_agent.py                 # Shared shell (logging, timing, errors, tracing)
│   ├── planner_agent.py              # Decides WHAT to run (ExecutionPlan); plans only
│   ├── scenario_agent.py             # Chooses one EXISTING Week 6 scenario
│   ├── optimization_agent.py         # Drives the Week 6 execution service (not OR-Tools)
│   ├── evaluation_agent.py           # Judges KPIs + before/after; benchmark comparison
│   ├── reporting_agent.py            # Renders markdown / JSON / text + recommendations
│   ├── tools.py                      # The ONLY seam to the platform (execution-service)
│   ├── crew.py                       # Real CrewAI Agent/Task/Crew (optional LLM mode)
│   └── coordinator.py                # The orchestrator that runs all five agents
├── dashboard/                        # Streamlit analytics dashboard (Week 8)
│   ├── app.py                        # Streamlit entry point (sidebar + routing)
│   ├── config.py                     # Dashboard settings (API base URL, limits)
│   ├── api_client.py                 # The ONLY seam to FastAPI (one per endpoint)
│   ├── components/                   # Reusable UI (kpi cards, charts, tables,
│   │                                 #   filters, agent trace, report viewer)
│   ├── pages/                        # One file per page (6 pages, each render())
│   └── utils/                        # Formatting + export helpers (no backend)
├── docs/
│   ├── dataset_overview.md           # Public dataset documentation
│   ├── logistics_data_model.md       # E-commerce → logistics data model
│   ├── future_database_design.md     # Early planned database design (Week 1)
│   ├── logistics_simulation.md       # How the simulation layer is built
│   ├── simulation_assumptions.md     # Every simulation modeling assumption
│   ├── database_design.md            # Why PostgreSQL/SQLAlchemy + architecture
│   ├── database_schema.md            # Exact tables, columns, keys, indexes
│   ├── api_architecture.md           # Backend layers, request lifecycle, roadmap
│   ├── fastapi_design.md             # Why FastAPI, DI, schemas vs. models
│   ├── rest_api_design.md            # REST conventions, methods, status codes
│   ├── optimization_architecture.md  # Engine layers, package, SOLID (Week 5)
│   ├── or_tools_design.md            # Why OR-Tools; LP/IP/CP/VRP; the models
│   ├── optimization_flow.md          # Runtime flow of each optimizer + responses
│   ├── future_scaling.md             # VRP, agents, caching, cloud, scaling
│   ├── optimization_execution.md     # (Week 6) execution layer + runtime flow
│   ├── optimization_metrics.md       # (Week 6) the 12 KPIs, how each is computed
│   ├── evaluation_framework.md       # (Week 6) before-vs-after evaluation
│   ├── scenario_execution.md         # (Week 6) scenarios + benchmarking
│   ├── agent_orchestration.md        # (Week 7) the AI orchestration layer overview
│   ├── crewai_design.md              # (Week 7) CrewAI integration + the two modes
│   ├── agent_flow.md                 # (Week 7) one request through all five agents
│   ├── dashboard_architecture.md     # (Week 8) dashboard layers + endpoints consumed
│   ├── dashboard_user_guide.md       # (Week 8) how to run and use every page
│   └── week8_dashboard_summary.md    # (Week 8) what was added + SDE relevance
├── notebooks/
│   ├── week0_dataset_analysis.py     # Profiles every CSV
│   ├── week1_data_cleaning.py        # Cleans raw CSVs → processed/
│   ├── week1_dataset_joins.py        # Joins files → one master table
│   ├── week2_generate_warehouses.py  # Sellers → warehouses (run first)
│   ├── week2_inventory_simulation.py # Stock levels per warehouse
│   ├── week2_vehicle_generation.py   # A delivery fleet per warehouse
│   ├── week2_disruption_generation.py# Traffic / weather / overload events
│   ├── week2_route_generation.py     # Warehouse → customer route estimates
│   ├── week3_load_database.py        # Loads processed/ + simulation/ → PostgreSQL
│   ├── week3_test_crud.py            # Exercises every CRUD function
│   ├── week4_api_demo.py             # Demonstrates the REST API (happy paths)
│   ├── week4_api_validation.py       # Demonstrates the API error handling
│   ├── week5_optimization_demo.py    # Demonstrates the four optimizers
│   ├── week5_validation.py           # Validates the optimization constraints
│   ├── week6_execution_demo.py       # (Week 6) run/simulate/history/metrics demo
│   ├── week6_benchmark_runner.py     # (Week 6) sweeps scenarios -> one report
│   ├── week6_validation.py           # (Week 6) execution-layer PASS/FAIL checklist
│   ├── week7_agents_demo.py          # (Week 7) autonomous decisions via /agents
│   ├── week7_validation.py           # (Week 7) orchestration-layer PASS/FAIL checklist
│   ├── week8_dashboard_demo.py       # (Week 8) dashboard walkthrough + endpoint checks
│   └── week8_validation.py           # (Week 8) dashboard PASS/FAIL checklist
├── benchmarks/                       # (Week 6) generated benchmark reports
│   └── week6_benchmark_report.md     # Written by week6_benchmark_runner.py
```

> `processed/` and `simulation/` are generated by the Week 1 and Week 2 scripts
> respectively and are not required in version control. The raw `data/` files
> are always treated as read-only.

## Progress

The project is built incrementally. Each week produces working code and
documentation while keeping the original dataset unchanged.

### Week 0 — Business & Dataset Understanding ✅

- [x] Project structure set up.
- [x] Dataset analysis script (`notebooks/week0_dataset_analysis.py`) that
      profiles every CSV: shape, columns, data types, missing values,
      duplicates, memory usage, and sample rows.
- [x] Public dataset documentation (`docs/dataset_overview.md`) covering each
      file, the table relationships, and the supply chain mapping.
- [x] Defined which data is **real** vs. what will be **simulated** later.

### Week 1 — Data Cleaning, Relationships & Logistics Data Modeling ✅

- [x] **Data cleaning** (`notebooks/week1_data_cleaning.py`) — reads the raw
      CSVs and writes validated copies to `processed/`: handles missing values
      per column, removes duplicate rows, validates coordinates, parses text
      timestamps to datetimes, and standardizes text. Originals are never
      modified.
- [x] **Dataset joins** (`notebooks/week1_dataset_joins.py`) — connects the
      cleaned files (orders → customers → order items → products → sellers →
      geolocation) into a single order-level master table.
- [x] **Logistics data modeling** (`docs/logistics_data_model.md`) — maps each
      entity to a logistics role and documents the modeling assumptions.
- [x] **Future database planning** (`docs/future_database_design.md`) — designs
      the tables (customers, orders, warehouses, inventory, products, routes,
      vehicles, disruptions, agent decisions) without writing SQL yet.

> Week 1 prepares the project for **Week 2 (logistics simulation)** by
> producing a clean, connected dataset and a documented data model and
> database plan. The backend, optimization, agents, and dashboards arrive in
> later weeks.

### Week 2 — Logistics Simulation Foundation ✅

The Olist data records online **sales**, not a running logistics operation, so
it has no warehouse capacity, stock levels, vehicles, live disruptions, or route
plans. Week 2 **generates a realistic simulated logistics layer on top of the
cleaned Week 1 data** — clearly separating real Olist data from simulated data
and documenting every assumption. All scripts read from `processed/`, write only
to `simulation/`, and use a fixed random seed for reproducibility; the raw
`data/` files are never modified.

- [x] **Warehouse generation** (`notebooks/week2_generate_warehouses.py`) —
      promotes the top Olist sellers by real shipped volume to warehouses
      (real location) with simulated capacity, utilization, and operating status.
- [x] **Inventory simulation** (`notebooks/week2_inventory_simulation.py`) —
      simulates stock levels, reorder thresholds, and inventory status per
      (warehouse, product), scaled from real sales volume.
- [x] **Vehicle simulation** (`notebooks/week2_vehicle_generation.py`) —
      generates a delivery fleet (vans and trucks) per warehouse with capacity,
      cost, speed, and availability.
- [x] **Disruption simulation** (`notebooks/week2_disruption_generation.py`) —
      generates traffic, weather, warehouse-overload, inventory-shortage, and
      road-closure events with severity, timing, and delay impact.
- [x] **Delivery route generation** (`notebooks/week2_route_generation.py`) —
      builds estimated warehouse → customer routes with distance, time, and cost
      computed from real coordinates (haversine). No optimization yet.
- [x] **Public documentation** — [`docs/logistics_simulation.md`](docs/logistics_simulation.md)
      (how the layer is built) and [`docs/simulation_assumptions.md`](docs/simulation_assumptions.md)
      (every modeling assumption).

> Week 2 produces the operational dataset the project stores in a real database
> in **Week 3**, later **optimizes** (route optimization), and **reacts to**
> (disruption-driven replanning). The route estimates here are deliberately
> simple — the optimization engine improves them in a later week.

### Week 3 — Database Foundation ✅

Weeks 0–2 produced data as CSV files (`processed/` real data, `simulation/`
simulated data). Week 3 moves that data into a real **PostgreSQL** database
behind a clean **SQLAlchemy** layer, so the future API, agents, and dashboard
can read and write shared, relationship-enforced, indexed data. The source CSVs
are never modified — they remain the reproducible inputs the database loads
from.

- [x] **Database layer** (`database/`) — settings loaded from a local `.env`
      (`config.py`), a SQLAlchemy engine + session factory + `Base`
      (`connection.py`), table creation (`init_db.py`), and a reusable CRUD /
      query API (`crud.py`). Importing the layer never opens a connection, so
      it is always safe to import.
- [x] **ORM models** (`models/`) — nine tables (`customers`, `sellers`,
      `products`, `orders`, `warehouses`, `inventory`, `vehicles`,
      `delivery_routes`, `disruptions`) with primary keys, foreign keys,
      relationships, indexes, and constraints. The schema is normalised and
      reserves nullable columns so OR-Tools and disruption replanning can attach
      later with no migration.
- [x] **Database loader** (`notebooks/week3_load_database.py`) — reads the
      Week 1 cleaned CSVs and Week 2 simulated CSVs and loads them into
      PostgreSQL in foreign-key order, with batched, re-runnable inserts
      (`ON CONFLICT DO NOTHING`), row-count validation, and orphan foreign-key
      checks. Read-only on the CSVs.
- [x] **CRUD layer + test** (`database/crud.py`,
      `notebooks/week3_test_crud.py`) — get/list/update/insert helpers used by
      later weeks, exercised end-to-end against the loaded data.
- [x] **Public documentation** — [`docs/database_design.md`](docs/database_design.md)
      (why PostgreSQL/SQLAlchemy, architecture, ERD, normalization, scaling, and
      how the future stack plugs in) and
      [`docs/database_schema.md`](docs/database_schema.md) (the exact tables,
      columns, keys, and indexes).

**Setup (local):**

```bash
pip install -r requirements.txt          # SQLAlchemy, psycopg, python-dotenv
cp .env.example .env                      # then set DATABASE_PASSWORD in .env
createdb supply_chain_optimizer           # one-time: create the database
python database/init_db.py                # create tables, indexes, foreign keys
python notebooks/week3_load_database.py   # load processed/ + simulation/ CSVs
python notebooks/week3_test_crud.py       # verify the CRUD functions
```

> Week 3 gives the project a persistent, queryable foundation. **Alembic** is
> installed for future schema migrations but is intentionally not initialised
> yet. Next up: the FastAPI backend reusing the same CRUD layer, then route
> optimization (OR-Tools) writing optimized assignments back into the reserved
> route/vehicle columns.

### Week 4 — FastAPI Backend Foundation ✅

Week 3 stored the data in PostgreSQL, reachable only from Python. Week 4 puts a
**FastAPI** REST API in front of it so any program — a dashboard, agents,
another service, or a script — can read and write the data over HTTP as JSON.
The backend **reuses the Week 3 database connection, SQLAlchemy models, and CRUD
layer unchanged** — no database logic is duplicated.

- [x] **Layered backend** (`api/`) — a clean, layered architecture where each
      layer only talks to the next: `Client → Router → Service → SQLAlchemy →
      PostgreSQL → JSON`. Routers are thin (HTTP only); all business logic lives
      in the service layer; only services touch the database.
- [x] **Seven REST resources** — `customers`, `warehouses`, `inventory`,
      `vehicles`, `routes`, `orders`, `disruptions`. Each supports `GET` (list),
      `GET` by id, `POST`, `PUT`, `PATCH`, `DELETE`, plus filtering, sorting,
      searching, and pagination via a consistent query interface.
- [x] **Pydantic schemas** (`api/schemas/`) — request/response/update/validation
      schemas per entity that validate all input at the boundary and control
      exactly which fields are exposed, keeping the API shape separate from the
      database shape.
- [x] **Service layer** (`api/services/`) — the business logic (e.g. inventory
      status is recomputed from the Week 2 stock rule on every change), reused by
      later weeks without going through HTTP.
- [x] **Validation & error handling** (`api/utils/`) — custom exceptions and
      handlers return a single, consistent JSON error envelope with correct
      status codes (`400/404/409/422/500`; `401/403` reserved for future auth).
      Raw SQL errors are never exposed — they are logged server-side.
- [x] **Automatic documentation** — Swagger UI at `/docs`, ReDoc at `/redoc`, and
      the OpenAPI spec at `/openapi.json`, all generated from the code.
- [x] **API test scripts** (`notebooks/week4_api_demo.py`,
      `notebooks/week4_api_validation.py`) — exercise every method, filtering,
      pagination, and the error paths, with clean explained output.
- [x] **Public documentation** — [`docs/api_architecture.md`](docs/api_architecture.md)
      (layers, request lifecycle, roadmap), [`docs/fastapi_design.md`](docs/fastapi_design.md)
      (why FastAPI, dependency injection, schemas vs. models), and
      [`docs/rest_api_design.md`](docs/rest_api_design.md) (REST conventions).

**Backend architecture:**

```
Client  (browser, dashboard, agent, script)
  │  HTTP request + JSON
  ▼
API Router      api/routers/*.py     (thin: no DB, no logic)
  ▼
Service Layer   api/services/*.py    (all business logic)
  ▼
SQLAlchemy      models/ + database/  (Week 3, reused)
  ▼
PostgreSQL      the Week 3 database
  ▼
JSON Response   Pydantic response schema → JSON
```

**Run the API (local):**

```bash
pip install -r requirements.txt          # adds fastapi, uvicorn, pydantic
python database/init_db.py                # (if not already) create tables
python notebooks/week3_load_database.py   # (if not already) load the data
uvicorn api.main:app --reload             # start the API server
# then open the interactive docs:
#   http://127.0.0.1:8000/docs            (Swagger UI)
#   http://127.0.0.1:8000/redoc           (ReDoc)
#   http://127.0.0.1:8000/openapi.json    (OpenAPI spec)
python notebooks/week4_api_demo.py        # demo the endpoints (no server needed)
python notebooks/week4_api_validation.py  # demo the error handling
```

**Request lifecycle (a read):** the server receives the HTTP request → FastAPI
matches the route and injects a per-request database session → the thin router
calls a service → the service queries via SQLAlchemy → the row is shaped by a
Pydantic response schema into JSON → the session is closed → the client receives
the response (or a clean error envelope).

**Future integrations (designed for, not implemented yet):** the layering keeps
the backend ready for what follows without a redesign — **OR-Tools** route
optimization (writes optimized assignments into the reserved route/vehicle
columns), **Redis** caching (wraps hot reads inside services), **CrewAI** agents
(call the same service functions), **authentication** (a router dependency, with
`401/403` already reserved), an interactive **dashboard** (consumes the existing
JSON endpoints), and **AWS** deployment (point the database URL at a managed
PostgreSQL via `.env`).

> Week 4 turns the stored data into a shared, documented, network-reachable
> service — the surface every later week builds on. Next up: **Week 5 route
> optimization (OR-Tools)**, which writes optimized vehicle assignments back into
> the reserved route columns through these same services.

### Week 5 — Optimization Engine ✅

Week 4 could **store and serve** the data; Week 5 makes **decisions** with it.
A new, self-contained **`optimization/`** package built on Google **OR-Tools**
computes optimized logistics plans, exposed through five new `/optimize`
endpoints on the existing FastAPI app. The engine is deliberately independent of
the web and the database — the service layer reads the Week 3 tables, maps rows
into plain input objects, calls a solver, and shapes the result into JSON —
which keeps it reusable by the future agents and the dashboard.

- [x] **Optimization engine** (`optimization/`) — a modular, database-free
      toolkit: `config.py` (tunable `OPT_*` settings), `utils.py` (haversine,
      timing, simulated demand), `cost_functions.py` (pricing), `constraints.py`
      (capacity/inventory rules), `solution_models.py` (input/output
      dataclasses), and one solver per problem.
- [x] **Four optimization problems** —
      **shipment assignment** (`assignment_solver.py`, CP-SAT: respect capacity,
      minimize unused capacity by consolidating),
      **warehouse selection** (`warehouse_selector.py`: nearest operating,
      in-stock warehouse per demand, else pending),
      **vehicle utilization** (`vehicle_optimizer.py`, CP-SAT: balance the load,
      avoid overloaded and idle vehicles), and
      **route optimization** (`route_optimizer.py`: nearest-neighbour heuristic
      with a `RoutingStrategy` interface reserved for a future VRP solver).
- [x] **FastAPI integration** — `GET /optimize/status` plus
      `POST /optimize/{assignment,warehouse,fleet,routes}`. Routers stay thin;
      the new `optimization_service` is the only layer touching both the database
      and the engine. Responses report success, cost, distance, vehicle
      utilization, unassigned shipments, and execution time.
- [x] **Reuses Weeks 2–4 unchanged** — the Week 3 SQLAlchemy models and the
      reserved `delivery_routes.vehicle_id` column, the Week 4 thin-router /
      service layering and error envelope, and the Week 2 haversine distance
      model (same `1.30` winding factor).
- [x] **Test scripts** (`notebooks/week5_optimization_demo.py`,
      `notebooks/week5_validation.py`) — the demo runs all four optimizers and
      shows the consolidate-vs-balance contrast; the validation script asserts
      every constraint (capacity, inventory, valid routes, assignment quality)
      and the error paths, printing a PASS/FAIL report.
- [x] **Public documentation** — [`docs/optimization_architecture.md`](docs/optimization_architecture.md)
      (layers, package, SOLID), [`docs/or_tools_design.md`](docs/or_tools_design.md)
      (why OR-Tools; LP / IP / CP / VRP; the CP-SAT models),
      [`docs/optimization_flow.md`](docs/optimization_flow.md) (runtime flow of
      each optimizer), and [`docs/future_scaling.md`](docs/future_scaling.md)
      (VRP, agents, caching, cloud, scaling).

**The four optimization problems:**

```
1. Shipment assignment  (CP-SAT)   assign shipments -> vehicles, respect
                                   capacity, MINIMIZE UNUSED CAPACITY
2. Warehouse selection  (greedy)   nearest operating, in-stock warehouse per
                                   demand; else mark PENDING
3. Vehicle utilization  (CP-SAT)   BALANCE the load across the fleet; avoid
                                   overloaded and idle vehicles
4. Route optimization   (heuristic) order a warehouse's stops with
                                   NEAREST-NEIGHBOUR; VRP interface reserved
```

**Run the optimizers (local):**

```bash
pip install -r requirements.txt          # adds ortools
uvicorn api.main:app --reload             # start the API (adds /optimize/*)
# then open the interactive docs at http://127.0.0.1:8000/docs, or:
python notebooks/week5_optimization_demo.py   # run all four optimizers
python notebooks/week5_validation.py          # validate the constraints
```

> Week 5 turns the served data into optimized plans behind a modular engine that
> is ready to grow. Next up: **Week 6 Redis caching** in front of the hot reads,
> and **Week 7 CrewAI agents** that call these same optimization services to plan
> — and replan around disruptions — autonomously.

### Week 6 — Optimization Execution Layer ✅

Week 5 could **run** a solver on demand; Week 6 turns the engine into a complete
backend **service** around it. A new **execution layer** takes one request and
produces a *recorded* outcome: it runs the optimizer (optionally under a **"what
if" scenario**), **measures** twelve KPIs, **evaluates** the plan against an
un-optimized baseline, and **stores** every run — all under a new `/optimization/*`
namespace, distinct from Week 5's `/optimize/*`. **Everything is additive**: no
Week 0–5 file is rewritten, and the Week 5 endpoints and engine are untouched.

- [x] **Execution engine modules** (`optimization/`, pure & database-free) —
      `execution_config.py` (KPI pricing tunables), `metrics.py` (the twelve
      KPIs), `evaluation.py` (before-vs-after + naive baselines), and
      `scenarios.py` (the scenario catalog + deterministic input transforms).
      They reuse the Week 5 solvers unchanged.
- [x] **Eleven scenarios** — High/Low Demand, Vehicle Breakdown, Warehouse
      Closed, Fuel Price Increase, Supplier Delay, Priority Orders (Part 4), plus
      Normal, Holiday, Demand Spike and Vehicle Failure for benchmarking. Each is
      a set of numeric changes applied to the optimizer's inputs before it solves.
- [x] **Twelve performance metrics** (Part 5) — total cost, travel distance,
      vehicle + warehouse utilization, inventory holding cost, stockouts, late
      deliveries, orders fulfilled, runtime, solver status, and the model size
      (constraints / variables). Stored cleanly on a new table.
- [x] **Evaluation framework** (Part 6) — a naive "before" plan (round-robin
      assignment; first-feasible warehouse; arrival-order routing) is scored by
      the same metrics as the optimized "after" plan, and the improvement is
      reported as signed percentages (cost, distance, utilization, delivery, …).
- [x] **Six REST endpoints** — `POST /optimization/run` (run + measure + evaluate
      + **store**), `POST /optimization/simulate` (a what-if, not stored), and
      `GET /optimization/{scenarios, metrics, history, {run_id}}`. Routers stay
      thin; the new `execution_service` is the only layer touching the database
      and the engine; the history reads reuse the Week 4 `BaseService`.
- [x] **Stored runs** — a new **`optimization_runs`** table
      (`models/optimization_run.py`) records each run's KPIs (promoted to columns)
      plus full JSON detail. It is created by `init_db.py`'s `create_all()`
      **with no migration** — the nine Week 3 tables are untouched.
- [x] **Benchmark runner** (Part 7) — `notebooks/week6_benchmark_runner.py`
      sweeps the benchmark scenarios through the API and writes **one** report to
      `benchmarks/week6_benchmark_report.md` (+ `.json`).
- [x] **Scripts** — `week6_execution_demo.py` (run / simulate / history /
      metrics), the benchmark runner, and `week6_validation.py` (a PASS/FAIL
      checklist — **31/31 checks pass**, including that Weeks 4 & 5 still work).
- [x] **Public documentation** — [`docs/optimization_execution.md`](docs/optimization_execution.md)
      (the execution architecture + runtime flow),
      [`docs/optimization_metrics.md`](docs/optimization_metrics.md) (the KPIs),
      [`docs/evaluation_framework.md`](docs/evaluation_framework.md) (before vs
      after), and [`docs/scenario_execution.md`](docs/scenario_execution.md)
      (scenarios + benchmarking).

**Execution flow:**

```
Client
  │  POST /optimization/run {optimizer, scenario, ...}
  ▼
api/routers/execution.py        (THIN: HTTP only)
  ▼
api/services/execution_service.py
  1. LOAD inputs from the Week 3 DB      (warehouses, vehicles, inventory, routes)
  2. APPLY a SCENARIO                    (optimization/scenarios.py)
  3. SOLVE                               (reused Week 5 OR-Tools solvers)
  4. MEASURE 12 KPIs                     (optimization/metrics.py)
  5. EVALUATE before vs after            (optimization/evaluation.py)
  6. STORE the run                       (optimization_runs table)
  ▼
OptimizationRunResult (JSON)  ◄── history/metrics read back via BaseService
```

**Run the execution layer (local):**

```bash
pip install -r requirements.txt          # no new deps in Week 6
python database/init_db.py                # creates optimization_runs (additive)
uvicorn api.main:app --reload             # adds /optimization/*
# then open http://127.0.0.1:8000/docs, or:
curl -X POST http://127.0.0.1:8000/optimization/run \
     -H "Content-Type: application/json" \
     -d '{"optimizer":"assignment","scenario":"high_demand","max_shipments":40}'
curl http://127.0.0.1:8000/optimization/history
curl http://127.0.0.1:8000/optimization/metrics

# or run the scripts (no server needed — they use the in-process TestClient):
python notebooks/week6_execution_demo.py     # run / simulate / history / metrics
python notebooks/week6_benchmark_runner.py    # sweep the benchmark scenarios
python notebooks/week6_validation.py          # the Week 6 PASS/FAIL checklist
```

**Sample results:** assignment under `normal` consolidated its work from **4
vehicles onto 2** (utilization **+27.5%**, now ~76.7%); under `high_demand` it hit
**91.5%** utilization with **20** deliveries flagged at-risk-of-late; route
optimization cut a 25-stop route by **~61%** vs the naive order; and the benchmark
showed `holiday` and `demand_spike` saturating the fleet to **100%** utilization
with **12** stockouts each, while `vehicle_failure` pushed **46** deliveries onto
stressed, near-capacity vehicles.

**Future AWS deployment (designed for, not implemented yet):** the execution
layer is cloud-ready by construction. The optimization engine is **database-free**
and every tunable comes from an environment variable (`OPT_*`, `API_*`,
`DATABASE_*`), so moving to AWS is a **configuration** change, not a code change:
point `DATABASE_*` at a managed **AWS RDS PostgreSQL** instance, run the
FastAPI app on **ECS/Fargate** (or behind an **API Gateway + Lambda** adapter)
with **uvicorn/gunicorn**, keep secrets in **AWS Secrets Manager / SSM Parameter
Store** (never in source), and create the additive `optimization_runs` table with
the same `python database/init_db.py`. The stored runs and the
`/optimization/metrics` aggregate become the data source for **CloudWatch**
dashboards, and a future **Redis (ElastiCache)** layer can cache hot solves — each
run already reports its runtime, so a cache wraps one service call. Nothing in the
engine or the service layer changes.

> Week 6 turns "we have a solver" into "we have a service that runs, measures,
> compares, benchmarks, and remembers optimizations." Next up: **Week 7 CrewAI
> agents** that call `POST /optimization/run`, read the KPIs and the before/after
> evaluation, and plan — and replan around disruptions — autonomously; then
> **Week 8** monitoring dashboards over the stored runs, and **Week 9** the AWS
> deployment sketched above.

### Week 7 — AI Multi-Agent Orchestration Layer ✅

Week 6 gave the project a service that runs, measures and remembers
optimizations; Week 7 puts an **AI multi-agent orchestration layer** on top of
it, turning the project into an **Autonomous Supply Chain Decision Platform**.
Five specialised agents — **Planner → Scenario → Optimization → Evaluation →
Reporting** — take a plain-language request and produce a complete, recorded,
explained decision, entirely by **orchestrating the existing Week 6 execution
service**. **Everything is additive**: no Week 0–6 file is rewritten (only the
router registry gains one line), and the agents **never touch OR-Tools
directly** — they drive the platform through a single tool seam.

- [x] **New `agents/` package** — `base_agent.py` (the shared shell: logging,
      timing, error handling, structured-output validation, execution tracing),
      the five agents (`planner_agent.py`, `scenario_agent.py`,
      `optimization_agent.py`, `evaluation_agent.py`, `reporting_agent.py`),
      `coordinator.py` (the orchestrator), `crew.py` (the real CrewAI assembly),
      `tools.py` (the only seam to the platform), `prompts.py`, `config.py`,
      `utils.py`. Each agent inherits `BaseAgent` and produces one typed contract.
- [x] **The five agents, each with one job** — the Planner decides *what* to run
      (never optimizes); the Scenario agent chooses one **existing** Week 6
      scenario (never invents one); the Optimization agent **calls the Week 6
      execution service** (never OR-Tools); the Evaluation agent judges the twelve
      KPIs + the before/after evaluation and adds a benchmark comparison; the
      Reporting agent renders **markdown + JSON + text** with recommendations and
      future improvements.
- [x] **CrewAI integrated, two orchestration modes** — a **deterministic**
      pipeline (the default: no LLM, no network, fully offline and reproducible)
      and an optional **crewai** mode (real `crewai.Agent`/`Task`/`Crew`) that
      adds natural-language reasoning/narration when `crewai` is installed and an
      LLM key is set. Both modes drive the **same** execution-service tools, so
      the numbers are always deterministic and correct; the layer **detects**
      which mode to use rather than hard-depending on CrewAI.
- [x] **Three REST endpoints** — `GET /agents/status` (which mode, agents, LLM),
      `POST /agents/decide` (make a decision and **store** the run), and
      `POST /agents/simulate` (a what-if, not stored). Routers stay thin; the new
      `agent_service` bridges FastAPI to the coordinator, passing the request's DB
      session straight through. A distinct `/agents/*` namespace leaves Week 5's
      `/optimize/*` and Week 6's `/optimization/*` untouched.
- [x] **Auditable by design** — every decision returns an **execution trace**
      (one timed, pass/fail step per agent), so an autonomous run is fully
      inspectable. An impossible request fails **loudly** (`success:false` with
      the failing step in the trace), never a 500.
- [x] **Scripts** — `week7_agents_demo.py` (three plain-language decisions +
      a full report) and `week7_validation.py` (a PASS/FAIL checklist —
      **42/42 checks pass**, including reasoning, reuse of the Week 6 service,
      resilience, and that Weeks 4, 5 & 6 still work).
- [x] **Public documentation** — [`docs/agent_orchestration.md`](docs/agent_orchestration.md)
      (the layer + architecture), [`docs/crewai_design.md`](docs/crewai_design.md)
      (the CrewAI integration + the two modes), and
      [`docs/agent_flow.md`](docs/agent_flow.md) (one request through all five agents).

**Orchestration architecture:**

```
User
  │  POST /agents/decide {goal, ...}
  ▼
api/routers/agents.py            (THIN: HTTP only)
  ▼
api/services/agent_service.py    (bridge → coordinator, passes the DB session)
  ▼
agents/coordinator.py            (the CrewAI Agent Orchestrator)
  ├─ PlannerAgent      → ExecutionPlan        (what to run)
  ├─ ScenarioAgent     → ScenarioDecision     (which existing Week 6 scenario)
  ├─ OptimizationAgent → OptimizationOutcome ─┐  (via agents/tools.py)
  ├─ EvaluationAgent   → EvaluationSummary    │
  └─ ReportingAgent    → AgentReport          │
                                              ▼
              api/services/execution_service.py   (Week 6, reused unchanged)
                → optimization/ engine (Week 5) → PostgreSQL (Week 3)
  ▼
OrchestrationResult (JSON: plan, scenario, KPIs, evaluation, report, trace)
```

**Run the orchestration layer (local):**

```bash
pip install -r requirements.txt          # crewai is OPTIONAL (see requirements.txt)
python database/init_db.py                # nothing new to create in Week 7
uvicorn api.main:app --reload             # adds /agents/*
# then open http://127.0.0.1:8000/docs, or:
curl http://127.0.0.1:8000/agents/status
curl -X POST http://127.0.0.1:8000/agents/decide \
     -H "Content-Type: application/json" \
     -d '{"goal":"optimize deliveries for a holiday peak, we are short on vans"}'

# or run the scripts (no server or LLM key needed — in-process TestClient, deterministic):
python notebooks/week7_agents_demo.py     # three autonomous decisions + a report
python notebooks/week7_validation.py      # the Week 7 PASS/FAIL checklist (42/42)
```

**Enabling the optional CrewAI (LLM) mode:** uncomment `crewai` in
`requirements.txt`, `pip install` it, and set an LLM key (`OPENAI_API_KEY`, or
`ANTHROPIC_API_KEY` with `AGENT_LLM_PROVIDER=anthropic`) — see `.env.example`.
`GET /agents/status` then reports the `crewai` mode, and each decision additionally
carries an LLM-authored `crew_narrative`. The deterministic numbers are unchanged;
if the LLM or network fails, the layer silently falls back to the deterministic
result. With no key set, everything runs deterministically out of the box.

> Week 7 turns "we have a service that runs, measures and remembers
> optimizations" into "we have an autonomous crew that **decides, executes,
> evaluates and explains** — safely orchestrating the platform it was given."
> Next up: **Week 8** monitoring dashboards over the stored runs and agent
> decisions, then **Week 9** the AWS deployment, and **Week 10** production.

### Week 8 — Analytics Dashboard & Visualization Layer ✅

Weeks 4–7 built a capable backend, but everything it produced was **JSON** —
demonstrable only through Swagger, `curl`, or the test scripts. Week 8 adds a
**Streamlit dashboard** that makes the existing system *visible*: it charts the
optimization history and KPIs, lets a user drive the agents from plain English,
draws the auditable five-agent execution trace, and renders the agent reports.
It is a **presentation layer only** — it consumes the existing Week 6
`/optimization` and Week 7 `/agents` endpoints over HTTP and **never** calls
OR-Tools, touches the database, or recomputes a KPI. **Everything is additive**:
a new `dashboard/` package; no Week 0–7 file is rewritten.

- [x] **Streamlit dashboard** (`dashboard/`) — a small, modular app (never one
      giant file): `app.py` (sidebar + connection status + page routing),
      `config.py` (one API base URL + display limits), and `api_client.py` (the
      **only** seam to FastAPI: one method per endpoint, one friendly error).
- [x] **Six pages** (`dashboard/pages/`) — **Overview** (aggregate KPIs +
      activity + trends + architecture), **Optimization History** (filter/sort/
      paginate + per-run drill-down), **Scenario Analysis** (catalog +
      comparisons + optional what-if simulate), **Agent Decisions** (run the
      crew from plain English), **Reports** (Markdown/Text/JSON), and **System
      Health** (backend + API availability).
- [x] **Reusable components** (`dashboard/components/`) — **KPI cards** (mapped
      to the Week 6 metrics; utilization shown as a percentage, not a 0–1
      value), **charts** (cost, distance, utilization, orders, stockouts by
      scenario; runtime by optimizer; runs over time; per-run improvement), a
      history **table** with backend-driven filters, an **execution-trace
      viewer** (Planner → Scenario → Optimization → Evaluation → Reporting, each
      step timed and pass/fail), and a **report viewer** (three-format tabs).
- [x] **Exports** (`dashboard/utils/export.py`) — download the history as CSV, a
      run as JSON, and an agent report as Markdown/JSON, via Streamlit download
      buttons.
- [x] **Resilient by design** — if the backend is offline, every page shows a
      friendly message instead of crashing; the sidebar shows a live
      Connected/Offline badge.
- [x] **Scripts** — `week8_dashboard_demo.py` (a printed walkthrough + live
      endpoint checks) and `week8_validation.py` (a PASS/FAIL checklist for the
      dashboard: imports, config, client, components, pages, formatting, export,
      resilience, and required files).
- [x] **Public documentation** — [`docs/dashboard_architecture.md`](docs/dashboard_architecture.md)
      (architecture + endpoints consumed + error handling + deployment path),
      [`docs/dashboard_user_guide.md`](docs/dashboard_user_guide.md) (how to run
      and use every page), and
      [`docs/week8_dashboard_summary.md`](docs/week8_dashboard_summary.md).

**Dashboard architecture (presentation only):**

```
Streamlit Dashboard  (dashboard/)
  │  HTTP, via dashboard/api_client.py (the ONE seam)
  ▼
FastAPI APIs         (/optimization/* Week 6, /agents/* Week 7, /health)
  ▼
Execution Service / Agent Service
  ▼
Optimization Engine  (Week 5, OR-Tools)
  ▼
PostgreSQL           (Week 3)
```

**Run the dashboard (local):**

```bash
pip install -r requirements.txt          # adds streamlit, plotly
uvicorn api.main:app --reload             # 1) start the backend (Weeks 4-7)
streamlit run dashboard/app.py            # 2) start the dashboard (opens :8501)

# verify + demo (the demo also checks the endpoints the dashboard uses):
python notebooks/week8_validation.py      # the Week 8 PASS/FAIL checklist
python notebooks/week8_dashboard_demo.py  # a guided walkthrough
```

Point the dashboard at a different backend by setting one environment variable
(`DASHBOARD_API_BASE_URL`, default `http://127.0.0.1:8000`) — no code change.

> The dashboard **does not compute optimization itself**. It **visualizes the
> existing Week 6 and Week 7 outputs**, consuming the FastAPI endpoints and
> never bypassing the execution service. Next up: **Week 9** — Docker + AWS
> deployment (containerize the API and the dashboard, point
> `DASHBOARD_API_BASE_URL` at the deployed backend — a configuration change,
> not a rewrite), then **Week 10** production hardening.
