# Optimization Architecture (Week 5)

This document explains the **architecture** of the Week 5 optimization engine:
the new `optimization/` package, how it plugs into the Week 4 FastAPI backend
and the Week 3 database, and the design principles that keep it modular and
ready for later weeks.

For *why* OR-Tools and the mathematics behind the solvers, see
[`or_tools_design.md`](or_tools_design.md); for the step-by-step data flow of
each optimizer see [`optimization_flow.md`](optimization_flow.md); for how
future weeks extend this see [`future_scaling.md`](future_scaling.md).

---

## What Week 5 adds

Weeks 3 and 4 gave the project a database and a REST API that could **store and
serve** supply-chain data. Week 5 adds the ability to **make decisions** with
that data: which vehicle carries which shipment, which warehouse should serve a
demand, how to balance a fleet, and what order to visit delivery stops in.

The engine is a new, self-contained package, `optimization/`, driven by Google
**OR-Tools**. It is exposed through five new endpoints under `/optimize` on the
existing FastAPI app.

---

## The layering (an extension of the Week 4 layering)

Week 4 established a strict layering: `Client → Router → Service → SQLAlchemy →
PostgreSQL`. Week 5 slots in cleanly, adding one new layer — the engine — that
the service calls:

```
Client  (browser, dashboard, agent, script)
  │  HTTP request + JSON  (e.g. POST /optimize/assignment)
  ▼
Optimization Router     api/routers/optimization.py     (thin: HTTP only)
  ▼
Optimization Service    api/services/optimization_service.py
  │   reads the Week 3 DB, maps rows -> engine inputs, calls a solver
  ├───────────────► SQLAlchemy models + PostgreSQL   (Week 3, reused)
  ▼
Optimization Engine     optimization/*.py              (OR-Tools, DB-free)
  ▼
Solution dataclass  →  Pydantic response schema  →  JSON
```

The key rule: **the engine never touches the database or HTTP.** It speaks only
in plain Python dataclasses. The service is the one place that knows about both
the database and the engine.

---

## The `optimization/` package

| File | Responsibility |
|------|----------------|
| `config.py` | Tunable settings (solver time limit, thresholds, safety caps) via pydantic-settings, `OPT_` prefix. |
| `utils.py` | Pure helpers: haversine distance, a `Timer`, safe maths, simulated package demand. |
| `cost_functions.py` | How a plan is **priced**: travel cost, unused capacity, utilization. |
| `constraints.py` | The **rules** a plan must obey: vehicle capacity, warehouse inventory, operating status. |
| `solution_models.py` | The plain input/output **dataclasses** the solvers speak in. |
| `assignment_solver.py` | Problem 1 — assign shipments to vehicles (CP-SAT). |
| `warehouse_selector.py` | Problem 2 — nearest in-stock warehouse per demand (greedy). |
| `vehicle_optimizer.py` | Problem 3 — balance the fleet (CP-SAT). |
| `route_optimizer.py` | Problem 4 — order stops into a short route (nearest-neighbour; VRP interface reserved). |

Each solver exposes both a **class** (`AssignmentSolver`, …) and a ready-made
**default instance** (`assignment_solver`, …), mirroring how the Week 4 entity
services expose both a class and a singleton.

---

## The four optimization problems

| # | Problem | Technique | Goal |
|---|---------|-----------|------|
| 1 | Shipment assignment | Integer programming (CP-SAT) | Respect capacity; **minimize unused capacity** by consolidating onto fewer vehicles. |
| 2 | Warehouse selection | Greedy nearest-feasible | Serve each demand from the **nearest** operating warehouse with enough stock; else mark **pending**. |
| 3 | Vehicle utilization | Integer programming (CP-SAT) | **Balance** shipments so no vehicle is overloaded and none sits idle. |
| 4 | Route optimization | Nearest-neighbour heuristic | Visit a warehouse's delivery stops in a **short** order; VRP-ready interface. |

Problems 1 and 3 are two views of the same fleet: the same variables and the
same capacity rule, but a different objective (consolidate vs. spread).

---

## How it reuses Weeks 3 and 4

- **Week 3 models, unchanged.** The service reads `warehouses`, `vehicles`,
  `inventory`, and `delivery_routes` through the existing SQLAlchemy models. No
  model or table was modified. The `delivery_routes.vehicle_id` column that
  Week 3 reserved is exactly where an assignment result can be written back.
- **Week 4 patterns, reused.** The router is thin; the service holds the logic
  and is the only layer touching the database; responses use Pydantic schemas
  with `from_attributes=True` (which read a solution dataclass's attributes the
  same way they read a SQLAlchemy row); errors flow through the same
  `AppError` handlers, so a bad request returns the same clean JSON envelope.
- **Week 2 distance model, reused.** Distances use the haversine formula scaled
  by the same `1.30` winding factor Week 2 used, so optimizer distances line up
  with the stored `estimated_distance_km`.

---

## SOLID principles in the design

- **Single Responsibility.** Each file does one thing: `constraints.py` says
  what is *allowed*, `cost_functions.py` says what is *better*, each solver
  searches for a plan, the service does the database mapping, the router does
  HTTP.
- **Open/Closed.** Routing is written behind a `RoutingStrategy` interface with
  a `NearestNeighbourStrategy` today and a reserved `VehicleRoutingProblem`
  strategy. A future week adds the VRP solver without changing any caller.
- **Dependency Inversion.** The engine depends on simple data (the input
  dataclasses), not on FastAPI or SQLAlchemy. High-level policy (the service)
  depends on abstractions (the solver interfaces), not the other way round.

This is what makes the engine reusable: the Week 7 CrewAI agents will call the
same service methods (or the solvers directly) without going through HTTP.

---

## A note on simulated shipment size

The Olist dataset records an order but **not** how many packages each delivery
contains. Because the vehicle-capacity constraints only become meaningful if
each shipment has a size, the service fills that gap with a **stable, simulated
package count** derived deterministically from the shipment id
(`optimization/utils.py::simulated_package_demand`). This follows the project's
long-standing discipline — established in Week 2 — of clearly separating real
Olist data from documented, reproducible simulated values.
