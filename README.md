# 🚚 Autonomous Supply Chain & Logistics Optimizer

> **An end-to-end supply-chain optimization platform combining a FastAPI backend, PostgreSQL persistence, Google OR-Tools solvers, deterministic five-agent orchestration (with optional CrewAI mode), a Streamlit dashboard, and an AWS EC2 deployment instrumented with CloudWatch.**

<p align="center">

**FastAPI • PostgreSQL • Google OR-Tools • Multi-Agent Orchestration • Streamlit • SQLAlchemy • AWS EC2**

</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-red) ![Google OR-Tools](https://img.shields.io/badge/Google_OR--Tools-orange) ![Multi-Agent](https://img.shields.io/badge/Multi--Agent-5--agent_orchestration-purple) ![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit) ![AWS EC2](https://img.shields.io/badge/AWS_EC2-Deployed-FF9900?logo=amazonaws)

</p>

<p align="center">

Turning a real-world e-commerce dataset into a modular, deployable logistics decision platform.

</p>

---

<a id="project-highlights" name="project-highlights"></a>
## 🌟 Project Highlights

|  |  |
|---|---|
| ✅ **FastAPI** REST backend (layered & documented) | ✅ **PostgreSQL** persistence via SQLAlchemy |
| ✅ **Google OR-Tools** optimization engine | ✅ **Deterministic five-agent** decision orchestration |
| ✅ **CrewAI** integration (optional LLM mode) | ✅ **Streamlit** analytics dashboard |
| ✅ **12-KPI evaluation** vs. a naive baseline | ✅ **Scenario simulation** (11 what-if scenarios) |
| ✅ **Persistent optimization history** | ✅ **Executive decision reporting** |
| ✅ **Deployed on AWS EC2** (systemd, Nginx, CloudWatch, SNS) | ✅ **Fully additive, modular design** |

**Verified at a glance** — `182/182` validation checks passed (weeks 5–8) · `360/360` live API requests succeeded (100% HTTP 200) · server-side CP-SAT solve `~17–79 ms` for a 50-shipment assignment (live) · reproducible deterministic benchmark with a byte-identical two-run SHA-256 fingerprint · AWS EC2 deployment with CloudWatch monitoring. All five benchmark scenarios returned successful solver outcomes under the configured limits — full detail and caveats in [Verified Engineering Results](#verified-results).

---

## 📚 Table of Contents

- [Overview](#overview)
- [Dashboard Tour](#dashboard-tour)
- **Screenshots** — [Dashboard Overview](#dashboard-overview) · [Optimization Engine](#optimization-engine) · [Autonomous Multi-Agent System](#autonomous-multi-agent-system) · [Executive Reporting](#executive-reporting) · [Analytics](#analytics)
- [System Architecture](#system-architecture)
- [How It Works](#how-it-works)
- [Core Capabilities](#core-capabilities)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Dataset](#dataset)
- [Verified Engineering Results](#verified-results)
- [Engineering Milestones](#engineering-milestones)
- [Future Roadmap](#future-roadmap)
- [Documentation](#documentation)
- [Skills Demonstrated](#skills-demonstrated)

---

<a id="overview" name="overview"></a>
## 📌 Overview

**What it is.** A production-style platform that transforms a real Brazilian e-commerce
dataset into an intelligent logistics optimizer — covering warehouse selection, vehicle
assignment, route optimization, KPI benchmarking, deterministic five-agent decision
orchestration, and an interactive analytics dashboard.

**Why it exists.** Real logistics teams don't just need a solver — they need a *system*
that can run an optimization under real-world conditions, measure the outcome, compare it
to a baseline, remember it, and explain it in business terms. This project demonstrates
that full loop, engineered as clean, layered, independently testable components.

**Architecture at a glance.** A **Streamlit** dashboard talks only to a **FastAPI**
backend; FastAPI delegates to service classes that either run a **direct optimization** or
drive an **autonomous five-agent crew**; both paths execute **Google OR-Tools** solvers and
persist every run in **PostgreSQL**.

The platform was built incrementally across nine structured engineering phases (0–8),
progressing from raw dataset analysis to an autonomous multi-agent optimization platform
(deterministic by default, with an optional CrewAI LLM mode).

---

<a id="dashboard-tour" name="dashboard-tour"></a>
## 🧭 Dashboard Tour

The Streamlit dashboard is a **presentation layer only** — it consumes the FastAPI
endpoints over HTTP and never calls the solver or database directly. It has six pages:

| Page | What it does |
|------|--------------|
| **Overview** | Aggregate KPIs, activity breakdown, trends, and the system architecture at a glance. |
| **Optimization History** | Browse, filter, sort, and paginate every stored run, then drill into a single run's detail. |
| **Scenario Analysis** | Explore the scenario catalog, compare stored runs by scenario, and run non-persisted what-if simulations. |
| **Agent Decisions** | Submit a plain-English goal and watch the five-agent crew plan, optimize, evaluate, and report. |
| **Reports** | Read and export the executive decision report (summary, KPIs, evaluation, risks, recommendations). |
| **System Health** | Live backend / API / agent status, latency metrics, the scenario catalog, and recent activity. |

---

<a id="dashboard-overview" name="dashboard-overview"></a>
## 🖥️ Dashboard Overview

### Overview Dashboard

The single-glance landing page: aggregate KPIs, activity breakdown, and trends across all
stored runs, plus the system architecture. Rendered by the **Overview** page from
`/optimization/metrics` and `/optimization/history`.

![Overview Dashboard](docs/images/Overview%20Dashboard.png)

### System Health Dashboard

A live operations board — backend/API/agent service status, response-time and latency
metrics, the scenario catalog, and recent activity. Rendered by the **System Health** page,
which probes the FastAPI endpoints and degrades gracefully when the backend is offline.

![System Health Dashboard](docs/images/System_Health_Dashboard.png)

---

<a id="optimization-engine" name="optimization-engine"></a>
## 🧮 Optimization Engine

### Business Scenarios

The catalog of eleven what-if scenarios (demand, resource, cost, supply, priority) that
transform optimizer inputs before solving. Shown on the **Scenario Analysis** page from
`GET /optimization/scenarios`.

![Business Scenarios](docs/images/Business%20Scenarios.png)

### Scenario What-if Simulation

Runs a chosen scenario as a **non-persisted** simulation and displays its KPIs — exploring
"what would happen?" without polluting the stored history. Produced by the **Scenario
Analysis** page via `POST /optimization/simulate`.

![Scenario What-if Simulation](docs/images/Scenario%20What-if%20Simulation.png)

### Optimization History

A filterable, sortable, paginated table of every stored run — all filtering/sorting/paging
is done by the backend. Rendered by the **Optimization History** page from
`GET /optimization/history`.

![Optimization History](docs/images/Optimization%20History.png)

### Optimization Run Details

A drill-down into one run: its twelve KPIs, before-vs-after evaluation, the applied scenario
changes, and metadata — with a JSON export. Served by `GET /optimization/{run_id}`.

![Optimization Run Details](docs/images/Optimization%20Run%20Details.png)

---

<a id="autonomous-multi-agent-system" name="autonomous-multi-agent-system"></a>
## 🤖 Autonomous Multi-Agent System

### Agent Decisions Input

The plain-English request form where a user states a business goal (with optional
overrides), then runs or simulates an autonomous decision. Powered by the **Agent
Decisions** page → `POST /agents/decide` and `POST /agents/simulate`.

![Agent Decisions Input](docs/images/Agent_Decisions_Input.png)

### Agent Decision Execution Plan

The Planner's execution plan and the selected scenario, plus the optimization outcome
(stored run vs. what-if). Generated by the **Planner**, **Scenario**, and **Optimization**
agents.

![Agent Decision Execution Plan](docs/images/Agent_Decision_Execution_Plan.png)

### Evaluation Summary Dashboard

The business-friendly evaluation: an overall verdict, KPI cards, a baseline-comparison
chart, and a "vs. normal" benchmark. Produced by the **Evaluation** agent.

![Evaluation Summary Dashboard](docs/images/Evaluation_Summary_Dashboard_Agent.png)

### Evaluation Trace & Recommendations

The auditable five-agent execution trace (each step timed and pass/fail) alongside the
actionable recommendations. Rendered from the agent execution trace and the **Reporting**
agent.

![Evaluation Trace & Recommendations](docs/images/Evaluation_Trace_Recommendations_Agent.png)

---

<a id="executive-reporting" name="executive-reporting"></a>
## 📄 Executive Reporting

### Reports Page

The executive decision report — executive summary, KPIs, evaluation, business risks,
recommendations, and roadmap — with Markdown/JSON export. Rendered by the **Reports** page
from the Reporting agent's output.

![Reports Page](docs/images/Reports_Page.png)

### Executive Report

A close-up of the structured executive report an operator or recruiter can read at a
glance. Generated by the **Reporting** agent (its Markdown, Text, and JSON renderings all
share one underlying structure).

![Executive Report](docs/images/Executive_Report.png)

---

<a id="analytics" name="analytics"></a>
## 📈 Analytics

### Scenario Analytics Chart

Comparative charts of stored runs grouped by scenario — cost, distance, utilization,
orders, and stockouts. Drawn by the **Scenario Analysis** page from the optimization
history.

![Scenario Analytics Chart](docs/images/Scenario%20Analytics%20Chart.png)

---

<a id="system-architecture" name="system-architecture"></a>
## 🏗️ System Architecture

![System Architecture](docs/images/system_architecture.png)

The platform is organized into **five clean layers**. The Streamlit dashboard is a
**presentation layer only** — it never touches the solver or the database. Every request is
routed through **FastAPI**, where the business logic lives. From there, an **autonomous
multi-agent system** coordinates planning, scenario selection, optimization, evaluation, and
reporting; the **Execution Service** is the single entry point that runs the **Google
OR-Tools** engine and persists each run in **PostgreSQL**.

Two execution modes share the same backend:

- **Direct optimization flow** — the user selects an optimizer and scenario directly:
  `User → Streamlit → FastAPI → Execution Service → OR-Tools → PostgreSQL`.
- **Autonomous agent flow** — the user submits a natural-language request, which the
  five-agent crew turns into an optimized, evaluated, and reported decision:
  `User → Streamlit → Coordinator → Planner → Scenario → Optimization → Evaluation → Reporting → Execution Service → OR-Tools → PostgreSQL`.

<details>
<summary>Architecture diagram (Mermaid source)</summary>

```mermaid
flowchart TB
    subgraph PRES["Presentation Layer"]
        U["User"] --> UI["Streamlit Dashboard"]
    end
    subgraph APP["Application Layer"]
        API["FastAPI"] --> CO["Coordinator"]
    end
    subgraph AGENTS["Autonomous Multi-Agent Layer"]
        direction LR
        P["Planner Agent"] --> S["Scenario Agent"] --> O["Optimization Agent"] --> E["Evaluation Agent"] --> R["Reporting Agent"]
    end
    subgraph OPT["Optimization Layer"]
        EX["Execution Service"] --> ORT["OR-Tools Optimization Engine"]
    end
    subgraph DATA["Persistence Layer"]
        PG[("PostgreSQL")]
    end

    UI --> API
    CO --> P
    R --> EX
    API -. "direct optimization flow" .-> EX
    EX --> PG
```

</details>

---

<a id="how-it-works" name="how-it-works"></a>
## 🔄 How It Works

How a request flows through the implemented system:

1. A user submits a request from the dashboard — a plain-language goal or scenario/optimizer parameters.
2. The dashboard calls the FastAPI backend over HTTP through a single API-client seam (`/agents/*` for agent decisions, `/optimization/*` for direct runs).
3. FastAPI validates the request against Pydantic schemas, returning a consistent JSON error envelope on invalid input.
4. A thin router delegates to the service layer (`agent_service` or `execution_service`) — the only layer that touches the database and the engine.
5. For agent-driven requests, the coordinator runs the five agents in sequence (Planner → Scenario → Optimization → Evaluation → Reporting) to decide *what* to run and *which* scenario to apply.
6. The execution service loads inputs from PostgreSQL, applies the scenario transform, and invokes the Google OR-Tools solvers.
7. Twelve KPIs are measured and evaluated against a naive baseline, producing signed before-vs-after improvement percentages.
8. Each completed run is stored in the `optimization_runs` table (KPIs + full JSON detail) as queryable history.
9. The result — plan, KPIs, evaluation, report, and execution trace — is returned as JSON.
10. The dashboard visualizes it: KPI cards, charts, history, the five-agent trace, and the generated reports.

---

<a id="core-capabilities" name="core-capabilities"></a>
## 🚀 Core Capabilities

- 🤖 Multi-agent orchestration for autonomous supply chain optimization
- 🚚 Vehicle assignment optimization using Google OR-Tools (CP-SAT)
- 🏭 Intelligent warehouse selection
- 🛣 Route optimization with configurable constraints
- 📊 Interactive Streamlit analytics dashboard
- ⚡ FastAPI REST backend with a modular service architecture
- 🗄 PostgreSQL integration for persistent storage
- 📈 12-KPI benchmarking and before-vs-after evaluation
- 🔄 Scenario analysis, what-if simulation, and optimization comparison
- ☁ Deployed on AWS EC2 with Nginx, systemd services, CloudWatch monitoring, and SNS alerts

---

<a id="technology-stack" name="technology-stack"></a>
## 🛠 Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11 |
| Backend | FastAPI |
| Frontend | Streamlit |
| Database | PostgreSQL |
| Optimization | Google OR-Tools |
| AI Orchestration | Custom multi-agent coordinator + optional CrewAI |
| Visualization | Plotly |
| ORM | SQLAlchemy |
| Deployment | AWS EC2 (systemd, Nginx, CloudWatch, SNS) |

> The system is **deployed on AWS EC2** (Amazon Linux 2023): the FastAPI backend and
> Streamlit dashboard run as **systemd services** behind an **Nginx** reverse proxy,
> with **PostgreSQL** on the instance and an attached **IAM role**. Operational health
> is instrumented via the **CloudWatch Agent** (EC2/OS metrics + centralized logs) and
> **CloudWatch Alarms** wired to an **SNS** topic with email alerting.

---

<a id="getting-started" name="getting-started"></a>
## ⚡ Getting Started

**Prerequisites:** Python 3.11 and a local PostgreSQL instance.

```bash
# 1) Install dependencies
pip install -r requirements.txt

# 2) Configure and create the database
cp .env.example .env                      # then set DATABASE_PASSWORD in .env
createdb supply_chain_optimizer           # one-time: create the database
python database/init_db.py                # create tables, indexes, foreign keys
python notebooks/week3_load_database.py   # load processed/ + simulation/ CSVs

# 3) Start the backend (FastAPI)
uvicorn api.main:app --reload             # http://127.0.0.1:8000/docs (Swagger)

# 4) Start the dashboard (Streamlit)
streamlit run dashboard/app.py            # http://localhost:8501
```

Point the dashboard at a different backend with one environment variable
(`DASHBOARD_API_BASE_URL`, default `http://127.0.0.1:8000`) — no code change.

<details>
<summary>Demo &amp; validation scripts (no server needed — in-process TestClient, deterministic)</summary>

```bash
python notebooks/week4_api_demo.py          # REST endpoints        + week4_api_validation.py
python notebooks/week5_optimization_demo.py # four optimizers       + week5_validation.py
python notebooks/week6_execution_demo.py    # run/simulate/history  + week6_validation.py   (46/46)
python notebooks/week7_agents_demo.py       # autonomous decisions  + week7_validation.py   (42/42)
python notebooks/week8_dashboard_demo.py    # dashboard walkthrough + week8_validation.py
```

**Optional CrewAI (LLM) mode:** uncomment `crewai` in `requirements.txt`, install it, and
set an LLM key (`OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` with
`AGENT_LLM_PROVIDER=anthropic`) — see `.env.example`. `GET /agents/status` then reports the
`crewai` mode and each decision carries an LLM-authored narrative. With no key set,
everything runs deterministically out of the box.

</details>

---

<a id="project-structure" name="project-structure"></a>
## 📂 Project Structure

```text
autonomous-supply-chain-logistics-optimizer/
│
├── agents/              # AI agent orchestration and coordination
├── api/                 # FastAPI backend
├── benchmarks/          # Performance benchmarking and KPI reports
├── dashboard/           # Interactive Streamlit dashboard
├── data/                # Public Olist e-commerce dataset (read-only)
├── database/            # Database connection and CRUD operations
├── docs/                # Technical documentation
├── models/              # Shared data and domain models
├── optimization/        # Vehicle, warehouse and route optimization
│
├── README.md
├── requirements.txt
└── .env.example         # Environment configuration
```

> `processed/` and `simulation/` are generated by the data-cleaning and simulation scripts
> respectively and are not required in version control. The raw `data/` files are always
> treated as read-only.

---

<a id="dataset" name="dataset"></a>
## 📊 Dataset

**Brazilian E-Commerce Public Dataset by Olist** — roughly 100,000 real, anonymized orders
placed between 2016 and 2018, including customers, sellers, products, payments, reviews,
delivery timestamps, and geographic coordinates.

- [`docs/dataset_overview.md`](docs/dataset_overview.md) — every file, its columns, how the tables connect, and the supply chain mapping.
- [`docs/logistics_data_model.md`](docs/logistics_data_model.md) — how the e-commerce data is reinterpreted as a logistics dataset, with explicit modeling assumptions.
- [`docs/future_database_design.md`](docs/future_database_design.md) — the planned database tables, columns, and relationships (design only).

---

<a id="verified-results" name="verified-results"></a>
## ✅ Verified Engineering Results

All figures below trace to a project script, a benchmark artifact, a database
query, or a live HTTP measurement against the deployed instance — not to manual
estimates. Modeled logistics KPIs (cost, distance, utilization) are **simulated
model outputs, not real money, real fleets, or real customer impact.**

### A. System scale

| Layer | Verified count |
|---|---|
| Ingested orders / customers | ~99,441 each |
| Products / sellers | 32,951 / 3,095 |
| Modeled warehouses | 150 |
| Modeled vehicles | 209 |
| Delivery routes | 10,000 |
| Inventory rows / disruptions | 12,362 / 80 |
| Scenarios · optimizers · KPIs · agents | 11 · 4 · 12 · 5 |

> `~99.4k orders` is the **ingested source-dataset scale**. Each optimization run
> operates on a **bounded shipment sample** (commonly `max_shipments=50`) — a single
> solve does **not** optimize all 99k orders at once.
> *Evidence: `SELECT count(*)` per table on the local PostgreSQL database; live
> `GET /optimization/scenarios`.*

### B. Optimization quality and reproducibility

Flagship deterministic benchmark — `assignment` optimizer, warehouse **WH-0003**
(deterministically selected), **50 shipments/run**, **seed 42**, 5 scenarios,
Python 3.11.9, OR-Tools 9.15.6755. Two independent full sweeps produced
**byte-identical stable business metrics**, keyed to the same SHA-256 input
fingerprint `32d26c59…f35994f0`.

Across five deterministic benchmark scenarios, the assignment optimizer produced
reproducible, capacity-feasible solutions and improved vehicle utilization and
delivery-service KPIs under the tested conditions. Outcomes varied by scenario and
objective, reflecting explicit trade-offs among utilization, consolidation, modeled
cost, distance, and late deliveries. All five scenarios returned successful solver
outcomes under the configured limits; detailed solver statuses are documented in the
[benchmark report](benchmarks/week6_benchmark_report.md).

Normal scenario, optimized vs. naive baseline:

| Metric | Baseline | Optimized | Change |
|---|---|---|---|
| Vehicle utilization | 44.35% | 59.76% | **+34.7%** (relative) |
| Vehicles used | 4 | 1 | consolidation 4 → 1 |
| Late deliveries | 10 | 0 | eliminated |
| Orders fulfilled | 50 | 50 | 50/50 |

The engine evaluated cost, distance, utilization, fulfillment, stockouts, and
late-delivery trade-offs across all 12 KPIs; the full per-scenario results are in the
benchmark artifacts linked below.

<details>
<summary>Benchmark scope and trade-offs</summary>

- Outcomes vary by optimizer objective and scenario. The assignment benchmark
  prioritizes order fulfillment and vehicle consolidation under hard vehicle-capacity
  constraints; it is **not** designed to directly minimize monetary cost, and it does
  **not** reorder route stops (route-distance optimization is a separate `routes`
  optimizer and is not claimed here).
- Full solver status per scenario and the complete cost / distance / utilization /
  fulfillment / stockout / late-delivery results are documented in the benchmark
  report: [`week6_benchmark_report.md`](benchmarks/week6_benchmark_report.md) ·
  [`week6_benchmark_report.json`](benchmarks/week6_benchmark_report.json).
- These are simulated logistics KPIs (model outputs), **not** real-world savings,
  real money, or customer impact.

</details>

<details>
<summary>Reproducibility scope &amp; formulas</summary>

- **Reproducible** = the stable business metrics (utilization, orders, stockouts,
  late deliveries, solver status, evaluation %) are identical when the input
  fingerprint, selected warehouse, code, configuration, Python version and OR-Tools
  version match. `runtime`, `run_id` and `created_at` are environment-dependent and
  excluded from the comparison.
- `utilization_gain% = (0.5976 − 0.4435) / 0.4435 × 100 = +34.7%` (relative %, not pp).
- `late_delivery_reduction% = (10 − 0) / 10 × 100 = 100%`.
- *Evidence: `benchmarks/week6_benchmark_report.{md,json}`;
  `notebooks/week6_benchmark_runner.py`; `notebooks/week6_reproducibility_check.py` (exit 0).*

</details>

### C. Validation and live AWS performance

- **182/182** automated validation checks pass across weeks 5–8 (20 / 46 / 42 / 74).
- **360/360** sequential live API requests succeeded — **0 failures, 100% HTTP 200**.
- Lightweight API latency: **median ~68–76 ms**, **p95 ~87–113 ms** (end-to-end).
- DB-backed optimization-history read: **median ~110 ms**, **p95 ~146 ms**.
- Live server-side CP-SAT assignment solve: **~17–79 ms** for 50 shipments.
- Deterministic five-agent workflow: **mean ~520 ms** end-to-end (3/3 successful runs).
- Live persistence proof: a labeled `POST` moved the AWS stored-run count **22 → 23**,
  confirmed via a separate `GET /optimization/metrics` read.

<details>
<summary>Required measurement caveats</summary>

- All latency figures were measured **sequentially (concurrency = 1)** — this was a
  correctness/reliability probe, **not** a sustained-load or scalability test.
- Public-API latency **includes the home → us-east-1 network round trip** (a ~50 ms
  floor); these are not server-only numbers.
- The **~520 ms** agent latency was **deterministic mode with no LLM calls** — it is
  not an LLM/CrewAI latency figure.
- The **17–79 ms** solve time applies to the tested live 50-shipment cases; it is
  not a universal solve-time guarantee. Runtime varies with scenario, warehouse, and
  constraint hardness; per-scenario runtimes are documented in the
  [benchmark report](benchmarks/week6_benchmark_report.md).
- *Evidence: validation via `notebooks/week{5,6,7,8}_validation.py` (in-process
  `TestClient`); live latency, solve-time and persistence from a controlled
  sequential probe of the deployed endpoint (raw measurement JSON retained locally).*

</details>

### D. AWS deployment and observability

- **AWS EC2** (Amazon Linux 2023), single instance.
- **Nginx** reverse proxy on port 80.
- **FastAPI** and **Streamlit** as persistent **systemd** services.
- **PostgreSQL** persistence on the instance; attached **IAM role**.
- **CloudWatch Agent** collecting EC2 and OS-level dimensions (CPU, network,
  EBS read/write, memory, disk, disk-I/O and process health) with **centralized
  log groups** for Nginx, FastAPI, Streamlit, PostgreSQL and the CloudWatch Agent.
- **CloudWatch alarms** wired to an **SNS** topic with **email alerting**.
- **Port isolation verified live:** only port **80** (Nginx) is publicly reachable;
  **8000** (FastAPI), **8501** (Streamlit) and **5432** (PostgreSQL) are **not**
  publicly reachable.

<details>
<summary>Scope of the deployment claims</summary>

CloudWatch/OS dimensions are reported as **monitored**, not with specific
average/peak values — no exported console statistic is published here, so no exact
figure is claimed. Not implemented / not claimed: HTTPS, custom domain, load
balancer, Auto Scaling, multi-AZ, high availability, CI/CD, Docker, Kubernetes,
Terraform, Secrets Manager, and any real AWS-dollar cost figure.

</details>

> These are results across the tested scenarios and a single-instance deployment,
> not universal guarantees. See the caveats above.

---

<a id="engineering-milestones" name="engineering-milestones"></a>
## 🧱 Engineering Milestones

Built in structured, **additive** phases — each delivering working, documented code without
rewriting earlier ones — tracing the system from raw dataset analysis to an autonomous,
multi-agent optimization platform. Full detail for each phase lives in [`docs/`](docs/).

| Phase | Focus | Status |
|:-----:|-------|:------:|
| 0 | Business & dataset understanding | ✅ |
| 1 | Data cleaning, relationships & logistics modeling | ✅ |
| 2 | Logistics simulation foundation | ✅ |
| 3 | PostgreSQL database foundation | ✅ |
| 4 | FastAPI backend foundation | ✅ |
| 5 | Google OR-Tools optimization engine | ✅ |
| 6 | Optimization execution layer (KPIs, evaluation, history) | ✅ |
| 7 | AI multi-agent orchestration layer | ✅ |
| 8 | Analytics dashboard & visualization | ✅ |

### Phase 0 — Business & Dataset Understanding ✅

Profiled every raw CSV (shape, dtypes, missing values, duplicates, memory, samples) and defined **real vs. simulated** data, with public dataset and supply-chain documentation.

📖 [`dataset_overview.md`](docs/dataset_overview.md)

### Phase 1 — Data Cleaning, Relationships & Logistics Modeling ✅

Cleaned the raw CSVs (originals untouched) into `processed/`, joined them into an order-level master table (orders → customers → items → products → sellers → geolocation), and documented the logistics data model and future database plan.

📖 [`logistics_data_model.md`](docs/logistics_data_model.md) · [`future_database_design.md`](docs/future_database_design.md)

### Phase 2 — Logistics Simulation Foundation ✅

Generated a realistic simulated logistics layer on the cleaned data — real vs. simulated kept separate, a fixed seed for reproducibility, and `data/` never modified: **warehouses** promoted from top real sellers, plus **inventory**, a **vehicle fleet**, **disruptions**, and haversine **routes**.

📖 [`logistics_simulation.md`](docs/logistics_simulation.md) · [`simulation_assumptions.md`](docs/simulation_assumptions.md)

### Phase 3 — PostgreSQL Database Foundation ✅

Moved the CSV data into **PostgreSQL** behind a clean **SQLAlchemy** layer with a reusable CRUD API and **nine normalized tables** (keys, relationships, indexes, constraints; nullable columns reserved for later phases). Re-runnable, FK-ordered loader with validation; source CSVs stay read-only.

📖 [`database_design.md`](docs/database_design.md) · [`database_schema.md`](docs/database_schema.md)

### Phase 4 — FastAPI Backend Foundation ✅

Put a layered **FastAPI** REST API in front of the database (`Router → Service → SQLAlchemy → PostgreSQL`), reusing Phase 3 unchanged. **Seven REST resources** with full CRUD plus filter/sort/search/paginate, **Pydantic** validation, a consistent JSON error envelope (`400/404/409/422/500`; `401/403` reserved for future auth), and auto **Swagger / ReDoc / OpenAPI**.

📖 [`api_architecture.md`](docs/api_architecture.md) · [`fastapi_design.md`](docs/fastapi_design.md) · [`rest_api_design.md`](docs/rest_api_design.md)

### Phase 5 — Google OR-Tools Optimization Engine ✅

Added a self-contained, **database-free** `optimization/` package on **Google OR-Tools** (`/optimize/*`) solving **four problems**: shipment assignment (CP-SAT), warehouse selection (greedy), vehicle utilization (CP-SAT), and route optimization (nearest-neighbour with a `RoutingStrategy` interface reserved for a future VRP solver). Reuses Phases 2–4 unchanged.

📖 [`optimization_architecture.md`](docs/optimization_architecture.md) · [`or_tools_design.md`](docs/or_tools_design.md) · [`optimization_flow.md`](docs/optimization_flow.md) · [`future_scaling.md`](docs/future_scaling.md)

### Phase 6 — Optimization Execution Layer ✅

Turned the solver into a complete backend **service**: run under a **scenario**, measure **12 KPIs**, **evaluate** against a naive baseline, and **store** every run (`/optimization/*`, new additive `optimization_runs` table). **Eleven scenarios**, six endpoints, and a reproducible benchmark runner. **Validation: 46/46 checks pass.** 

📖 [`optimization_execution.md`](docs/optimization_execution.md) · [`optimization_metrics.md`](docs/optimization_metrics.md) · [`evaluation_framework.md`](docs/evaluation_framework.md) · [`scenario_execution.md`](docs/scenario_execution.md)

### Phase 7 — AI Multi-Agent Orchestration Layer ✅

Added a **five-agent crew** (Planner → Scenario → Optimization → Evaluation → Reporting) that turns a plain-language request into a recorded, explained decision by orchestrating the Phase 6 service — **never touching OR-Tools directly**. Two modes (**deterministic** default + optional **CrewAI** LLM), three endpoints, and an **auditable execution trace** per decision. **Validation: 42/42 checks pass.**

📖 [`agent_orchestration.md`](docs/agent_orchestration.md) · [`crewai_design.md`](docs/crewai_design.md) · [`agent_flow.md`](docs/agent_flow.md)

### Phase 8 — Analytics Dashboard & Visualization ✅

Added a **Streamlit** dashboard (a **presentation layer only** — it consumes the APIs and never recomputes a KPI): **six pages**, reusable KPI cards / charts / execution-trace viewer / report viewer, CSV/JSON/Markdown exports, and resilient offline handling.

📖 [`dashboard_architecture.md`](docs/dashboard_architecture.md) · [`dashboard_user_guide.md`](docs/dashboard_user_guide.md) · [`week8_dashboard_summary.md`](docs/week8_dashboard_summary.md)

---

<a id="future-roadmap" name="future-roadmap"></a>
## 🛣 Future Roadmap

Planned milestones that extend the current Phase 0–8 implementation:

- **HTTPS & custom domain** — add TLS termination and a domain name in front of the existing Nginx reverse proxy.
- **Secrets & configuration management** — move credentials into AWS Secrets Manager / SSM Parameter Store.
- **Caching layer** — add Redis (ElastiCache) in front of hot reads and repeated solves.
- **Authentication & authorization** — enable the reserved `401/403` paths with API auth and RBAC.
- **Schema migrations** — initialize the already-installed Alembic for versioned schema changes.
- **Deeper observability** — add a custom CloudWatch dashboard and extend the existing CloudWatch metrics/alarms with application-level KPIs from stored `optimization_runs` and `/optimization/metrics`.
- **CI/CD pipeline** — automate the existing validation scripts on every change.
- **Advanced route optimization** — implement a full VRP solver behind the reserved `RoutingStrategy` interface.

---

<a id="documentation" name="documentation"></a>
## 📖 Documentation

Full technical documentation lives in [`docs/`](docs/):

| Area | Documents |
|------|-----------|
| **Dataset & modeling** | [dataset_overview](docs/dataset_overview.md) · [logistics_data_model](docs/logistics_data_model.md) · [logistics_simulation](docs/logistics_simulation.md) · [simulation_assumptions](docs/simulation_assumptions.md) |
| **Database** | [database_design](docs/database_design.md) · [database_schema](docs/database_schema.md) · [future_database_design](docs/future_database_design.md) |
| **Backend API** | [api_architecture](docs/api_architecture.md) · [fastapi_design](docs/fastapi_design.md) · [rest_api_design](docs/rest_api_design.md) |
| **Optimization** | [optimization_architecture](docs/optimization_architecture.md) · [or_tools_design](docs/or_tools_design.md) · [optimization_flow](docs/optimization_flow.md) · [future_scaling](docs/future_scaling.md) |
| **Execution & evaluation** | [optimization_execution](docs/optimization_execution.md) · [optimization_metrics](docs/optimization_metrics.md) · [evaluation_framework](docs/evaluation_framework.md) · [scenario_execution](docs/scenario_execution.md) |
| **Agents** | [agent_orchestration](docs/agent_orchestration.md) · [crewai_design](docs/crewai_design.md) · [agent_flow](docs/agent_flow.md) |
| **Dashboard** | [dashboard_architecture](docs/dashboard_architecture.md) · [dashboard_user_guide](docs/dashboard_user_guide.md) · [week8_dashboard_summary](docs/week8_dashboard_summary.md) |

---

<a id="skills-demonstrated" name="skills-demonstrated"></a>
## 🧠 Skills Demonstrated

- Backend API development with FastAPI and layered, service-oriented design
- PostgreSQL database design and SQLAlchemy ORM integration
- Google OR-Tools optimization (assignment, utilization, routing, warehouse selection)
- KPI measurement, baseline evaluation, scenario simulation, and benchmarking
- Multi-agent orchestration (deterministic + optional CrewAI LLM mode)
- Streamlit dashboard development and data visualization with Plotly
- REST API design, validation, error handling, and automatic documentation
- Modular Python project organization and separation of concerns
- Testing/validation workflows and reproducible, additive engineering
- AWS EC2 deployment with systemd services, an Nginx reverse proxy, CloudWatch monitoring, and SNS alerting
