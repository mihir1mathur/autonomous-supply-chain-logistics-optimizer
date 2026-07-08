# Future Scaling (Week 5)

This document looks **forward**: how the Week 5 optimization engine is designed
to grow — into a full Vehicle Routing Problem (VRP) solver, into autonomous
agents that call it, into caching, and onto cloud infrastructure — and what to
watch as the data and load grow.

For the current design see
[`optimization_architecture.md`](optimization_architecture.md).

---

## Designed-for extension points

The engine deliberately leaves clean seams for later work, so future weeks add
capability without rewrites:

- **A real VRP solver.** Routing is written behind a `RoutingStrategy`
  interface. `NearestNeighbourStrategy` is implemented now; a
  `VehicleRoutingProblem` strategy is reserved (it currently raises
  `NotImplementedError`). A later week drops OR-Tools' routing library
  (`RoutingModel`, with capacities and time windows) behind that interface, and
  every caller — service, router, scripts — is unchanged.
- **Writing plans back to the database.** Week 3 reserved
  `delivery_routes.vehicle_id` as a nullable column. An assignment result can be
  persisted there through the existing Week 4 route service — no schema change
  and no migration needed.
- **Swappable objectives.** Cost and balance live in `cost_functions.py`; the
  rules live in `constraints.py`. New objectives (minimise cost, minimise
  lateness, respect priority) or new constraints (weight as well as package
  count, driver hours) are added in those files, not scattered through the
  solvers.
- **Tunable without code.** Every knob — solver time limit, thresholds, safety
  caps, winding factor — is an `OPT_*` environment setting, so behaviour is
  tuned per environment with no code change.

---

## How later weeks build on this

| Week / feature | How it uses the Week 5 engine |
|----------------|-------------------------------|
| **Redis caching** | Wrap the read-heavy `status` and repeated warehouse-selection lookups in a cache dependency inside the service. The engine is deterministic, so identical inputs can safely return a cached plan. |
| **CrewAI agents** | Autonomous planning agents call the **same** `optimization_service` methods (or the solvers directly) — no HTTP required — to decide assignments and routes, then act on the results. The database-free engine is exactly what makes this reuse safe. |
| **Disruption replanning** | When a disruption is recorded (a blocked road, an overloaded warehouse), an agent re-runs the affected optimizer with the changed inputs and writes the new plan back — the "react and replan" loop the project has been building toward. |
| **Dashboard** | A Streamlit dashboard calls the existing `/optimize/*` JSON endpoints to visualise assignments, fleet balance, and optimized routes on a map. |
| **AWS deployment** | Nothing in the engine is host-specific; point the database URL at a managed PostgreSQL via `.env` and the optimizers run unchanged. |

---

## How agents will invoke the optimization APIs

Two integration styles are available, and both are supported by the current
design:

1. **Over HTTP** — an agent (or any external service) sends
   `POST /optimize/assignment` and reads the JSON response. This is the loosely
   coupled path: the agent needs only the URL and the request shape.
2. **In-process** — an agent running inside the same application imports
   `optimization_service` and calls `optimize_assignment(db, …)` directly,
   skipping the HTTP round-trip. This is faster and is possible precisely
   because all the logic lives in the service and the engine, not in the router.

A typical autonomous loop: *observe* (read current shipments, fleet, and any
active disruptions) → *decide* (call the relevant optimizer) → *act* (write the
chosen `vehicle_id`/route back through the Week 4 services) → *repeat* when the
situation changes.

---

## Scaling considerations as data and load grow

- **Problem size.** CP-SAT models grow with (shipments × vehicles). The engine
  already keeps models small by solving **per warehouse** and by clamping each
  request to the `OPT_MAX_*` caps. For very large sites, raise the solver time
  limit or partition further (e.g. by region or delivery day).
- **Solution quality vs. time.** The time limit trades optimality for
  responsiveness: a longer limit yields provably better plans, a shorter one
  returns faster. Tune `OPT_SOLVER_TIME_LIMIT_SECONDS` per environment.
- **Route heuristic vs. exact.** Nearest-neighbour scales to many stops
  instantly but is not optimal. When route quality matters more than latency,
  the reserved VRP strategy (with OR-Tools' local-search metaheuristics) is the
  upgrade path.
- **Concurrency.** Solves are CPU-bound. Under heavy load, run them on a worker
  pool or a background queue rather than inline in the request, and cap CP-SAT's
  worker threads (`OPT_SOLVER_WORKERS`) so concurrent solves do not oversubscribe
  the CPU.
- **Real shipment sizes.** The simulated package demand is a stand-in. If a
  future data source provides true per-shipment package counts or weights, feed
  those into `ShipmentInput` instead — no solver change is required.

---

## Summary

Week 5 turns the stored, served data into **decisions**, behind a modular engine
that is independent of the web and the database. The strategy interface, the
reserved database column, the environment-driven settings, and the reusable
service methods are all in place so the next steps — a full VRP solver, caching,
autonomous agents, disruption replanning, a dashboard, and cloud deployment —
plug in without a redesign.
