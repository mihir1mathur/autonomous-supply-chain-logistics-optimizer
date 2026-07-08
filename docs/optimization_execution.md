# Optimization Execution Layer (Week 6)

Week 5 gave the project an optimization **engine** (`optimization/`) and a bridge
service that could **run a solver on demand** behind `/optimize/*`. Week 6 wraps
that engine in an **execution layer**: a service that turns a single request into
a complete, *recorded* outcome — run it (optionally under a scenario), **measure**
its KPIs, **evaluate** it against an un-optimized baseline, and **store** it — all
exposed under a new `/optimization/*` namespace.

This document describes the Week 6 architecture and runtime flow. It complements
the Week 5 [`optimization_architecture.md`](optimization_architecture.md) (the
engine's internal design), and the three companion Week 6 docs:
[`optimization_metrics.md`](optimization_metrics.md) (the KPIs),
[`evaluation_framework.md`](evaluation_framework.md) (before vs after), and
[`scenario_execution.md`](scenario_execution.md) (the scenarios).

> **Everything in Week 6 is additive.** No Week 0–5 file is rewritten. The Week 5
> `/optimize/*` endpoints and the `optimization_service` are untouched; Week 6
> adds new modules alongside them.

---

## Where Week 6 sits

```
Client  (browser, dashboard, agent, script)
  │  POST /optimization/run  (or /simulate, GET /optimization/history, ...)
  ▼
api/routers/execution.py         THIN router (HTTP only)         [Week 6, new]
  ▼
api/services/execution_service.py    the EXECUTION LAYER          [Week 6, new]
  │   1. load inputs from the DB (Week 3 models)
  │   2. apply a SCENARIO            optimization/scenarios.py     [Week 6, new]
  │   3. SOLVE                       optimization/*_solver.py      [Week 5, reused]
  │   4. MEASURE KPIs                optimization/metrics.py       [Week 6, new]
  │   5. EVALUATE before vs after    optimization/evaluation.py    [Week 6, new]
  │   6. STORE the run               models/optimization_run.py    [Week 6, new]
  ▼
optimization_runs table  ◄── read back by ──►  api/services/optimization_run_service.py
  (PostgreSQL, Week 3 engine)                   (subclasses the Week 4 BaseService)
```

The layering rule from Week 4 is preserved: **routers are thin**, all business
logic lives in the service layer, and only the service touches the database and
the engine. The Week 5 engine stays **database-free and FastAPI-free** — the
execution service maps rows in and JSON out.

---

## The six endpoints

All under the `/optimization` prefix (distinct from Week 5's `/optimize`).

| Method & path | Purpose |
|---------------|---------|
| `POST /optimization/run` | Run one optimization under a scenario, measure it, evaluate it, and **store** it. |
| `POST /optimization/simulate` | The same, but a throwaway **what-if** (not stored). |
| `GET /optimization/scenarios` | The catalog of available scenarios. |
| `GET /optimization/metrics` | Aggregate KPIs across the stored runs. |
| `GET /optimization/history` | List past runs (filter / search / sort / paginate). |
| `GET /optimization/{run_id}` | One stored run in full. |

> The Week 6 goals list `POST /optimize` and `POST /simulate`. Because Week 5
> already owns the `/optimize` prefix, Week 6 groups its endpoints under
> `/optimization` to avoid clobbering Week 5 — so `POST /optimize` maps to
> `POST /optimization/run` here. The literal paths (`/run`, `/simulate`,
> `/scenarios`, `/metrics`, `/history`) are declared **before** `/{run_id}` so a
> request for `/optimization/metrics` is never read as a run whose id is
> "metrics".

---

## Runtime flow — `POST /optimization/run`

Request (all optional): `optimizer`, `scenario`, `warehouse_id`, `max_shipments`,
`max_stops`, `sample_size`, `strategy`, `reserve_inventory`, `evaluate`.

```
Router: run_optimization(payload)
  -> ExecutionService.run(db, optimizer, scenario, ...)
       1. VALIDATE optimizer + scenario        (bad -> clean 400)
       2. LOAD    the real inputs from the Week 3 DB (warehouses, vehicles,
                  inventory, delivery routes) - the same rows Week 5 reads
       3. SCENARIO apply_scenario(scenario, shipments, vehicles, warehouses, stock)
                  -> modified COPIES + a list of what changed
       4. SOLVE   the reused Week 5 solver (assignment/fleet/routes/warehouse)
       5. MEASURE metrics_from_*(solution, context) -> RunMetrics (12 KPIs)
       6. EVALUATE build an un-optimized baseline, evaluate(before, after)
       7. STORE   insert one OptimizationRun row (unless /simulate)
  -> a result dict -> OptimizationRunResult (JSON)
```

The response carries the `run_id` (when stored), the `scenario_changes` applied,
the full `metrics` block, and the before-vs-after `evaluation`.

`POST /optimization/simulate` is identical but sets `persist=False`: it computes
everything and returns it, but writes nothing — a safe what-if.

---

## Persistence — the `optimization_runs` table

Every stored run is one row in a **new** table (see
`models/optimization_run.py`). It is created by `database/init_db.py`'s
`create_all()`, which only ever adds tables that do not exist — so running it
after Week 6 adds `optimization_runs` and leaves every Week 3 table untouched
(**no migration**).

A row holds the run's identity and context (`run_id`, `created_at`, `scenario`,
`optimizer`, `warehouse_id`), the **twelve KPIs promoted to columns** (so history
and the metrics aggregate can query and sort them directly), and three JSON blobs
for the full detail (`metrics`, `evaluation`, `details`).

The read side reuses the Week 4 `BaseService` unchanged:
`OptimizationRunService` subclasses it, declares its safelists, and adds one
custom `aggregate_metrics()` query for `GET /optimization/metrics`.

---

## What is reused, unchanged

| From | Reused by Week 6 |
|------|------------------|
| Week 5 | the four solver singletons (`assignment_solver`, `vehicle_optimizer`, `route_optimizer`, `warehouse_selector`) and the input/output dataclasses |
| Week 5 | the `OPT_*` caps (`max_shipments_per_request`, …) and the winding factor |
| Week 4 | `BaseService` (list/get/paginate), the pagination envelope, and the one-JSON-error envelope + handlers (a bad optimizer → 400, missing warehouse → 404, invalid body → 422) |
| Week 3 | the SQLAlchemy models and the lazy engine/session |
| Week 2 | the haversine × 1.30 winding-factor distance model and the `estimated_distance_km` leg distances |

---

## Errors

Optimization-execution errors flow through the **same** Week 4 exception
handlers, so the caller always sees `{ "error": { "code", "message" } }`:

| Situation | Status |
|-----------|--------|
| Unknown `optimizer` or `scenario` | `400` |
| Unknown `warehouse_id` | `404` |
| Unknown `run_id` (get by id) | `404` |
| Reserved `vrp` strategy, or unknown strategy | `400` |
| Invalid body (e.g. `sample_size` = 0) | `422` |
| Warehouse left with no vehicles by a scenario | `400` |

No error ever leaks a stack trace or raw SQL.

---

## Trying it

```bash
python database/init_db.py                    # creates optimization_runs (additive)
uvicorn api.main:app --reload
# then, in the Swagger UI at /docs, or:
curl -X POST http://127.0.0.1:8000/optimization/run \
     -H "Content-Type: application/json" \
     -d '{"optimizer":"assignment","scenario":"high_demand","max_shipments":40}'
curl http://127.0.0.1:8000/optimization/history
curl http://127.0.0.1:8000/optimization/metrics

# or run the scripts (no server needed - they use the in-process TestClient):
python notebooks/week6_execution_demo.py      # run / simulate / history / metrics
python notebooks/week6_benchmark_runner.py    # sweep the benchmark scenarios
python notebooks/week6_validation.py          # the Week 6 PASS/FAIL checklist
```
