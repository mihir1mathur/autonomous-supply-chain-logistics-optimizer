# Optimization Flow (Week 5)

This document walks through **what actually happens at runtime** for each of the
five optimization endpoints: the request, the database reads, the mapping into
engine inputs, the solve, and the response. It complements the *structure* in
[`optimization_architecture.md`](optimization_architecture.md) and the *maths*
in [`or_tools_design.md`](or_tools_design.md).

---

## The endpoints

All optimization endpoints live under the `/optimize` prefix.

| Method & path | Purpose |
|---------------|---------|
| `GET /optimize/status` | Engine readiness, OR-Tools version, solvers, settings. |
| `POST /optimize/assignment` | Assign a warehouse's shipments to its vehicles. |
| `POST /optimize/warehouse` | Choose the nearest in-stock warehouse per demand. |
| `POST /optimize/fleet` | Balance shipments evenly across the fleet. |
| `POST /optimize/routes` | Order a warehouse's stops into a short route. |

`GET` is used for `status` (it only reads fixed capability info); `POST` is used
for the optimizers because each takes a request body and performs a computation.

Every optimizer request is happy with an **empty body** (`{}`): the service
picks a sensible default target (a warehouse that has both vehicles and routes,
or a sample of demands built from real data), so each endpoint is runnable with
zero setup and can then be narrowed with explicit parameters.

---

## Common response fields

As the Week 5 goals require, every optimizer response reports, where relevant:
**success**, **cost**, **distance**, **vehicle utilization**, **unassigned
shipments**, and **execution time** (`execution_time_ms`, measured around the
solve). A human-readable `message` summarises the outcome, and `status` carries
the solver status (`OPTIMAL` / `FEASIBLE` / `OK`).

---

## 1. Shipment assignment — `POST /optimize/assignment`

Request (all optional): `warehouse_id`, `max_shipments`.

```
Router: optimize_assignment(payload)
  -> Service.optimize_assignment(db, warehouse_id, max_shipments)
       1. resolve the warehouse (given, or the one with the most available
          vehicles that also has routes)
       2. load its delivery routes as ShipmentInput (with a simulated package
          size and the Week 2 estimated_distance_km as the leg distance)
       3. load its AVAILABLE vehicles as VehicleInput (capacity_packages, rate)
       4. assignment_solver.solve(shipments, vehicles)   # CP-SAT
  -> AssignmentSolution -> AssignmentResponse (JSON)
```

Key response fields: `assignments` (shipment → vehicle), `vehicle_loads`
(per-vehicle packages/capacity, utilization, unused capacity), `vehicles_used`,
`average_vehicle_utilization`, `total_distance_km`, `total_cost`,
`unassigned_shipments`, `constraint_violations` (always `0`).

The objective consolidates onto as few vehicles as possible, so the vehicles
that *are* used come back tightly packed.

---

## 2. Warehouse selection — `POST /optimize/warehouse`

Request (all optional): `demands` (explicit list), `sample_size`,
`reserve_inventory`.

```
Router: optimize_warehouse(payload)
  -> Service.select_warehouses(db, demands, sample_size, reserve_inventory)
       1. if no demands given, sample `sample_size` from real data:
          - products stocked in the most warehouses (so there are choices)
          - real destinations from delivery routes
          - a simulated, varied quantity (some exceed stock -> pending)
       2. load all warehouses as WarehouseInput (location + operating_status)
       3. load the stock for the demanded products: (warehouse, product) -> level
       4. warehouse_selector.solve(demands, warehouses, stock, reserve_inventory)
  -> WarehouseSelectionSolution -> WarehouseSelectionResponse (JSON)
```

For each demand the selector keeps only warehouses that are **operating** and
**hold enough stock**, then picks the **nearest** (haversine × winding factor).
If none qualifies, the demand is **pending**. With `reserve_inventory` on
(default), each fulfilment decrements the tracked stock so two demands cannot be
promised the same units.

Key response fields: `choices` (each with `selected_warehouse_id`, `distance_km`,
`status` = assigned/pending, a `reason`), `assigned_count`, `pending_count`,
`average_distance_km`.

---

## 3. Vehicle utilization — `POST /optimize/fleet`

Request (all optional): `warehouse_id`, `max_shipments`.

```
Router: optimize_fleet(payload)
  -> Service.optimize_fleet(db, warehouse_id, max_shipments)
       (same warehouse resolution and loading as assignment)
       -> vehicle_optimizer.solve(shipments, vehicles)   # CP-SAT, minimize peak
  -> FleetUtilizationSolution -> FleetResponse (JSON)
```

Same inputs as assignment, opposite emphasis: it **spreads** the load to
minimize the busiest vehicle's utilization. Key response fields:
`average_utilization`, `min_utilization`, `max_utilization`,
`utilization_spread` (max − min; lower is better balanced), `overloaded_vehicles`
and `underutilized_vehicles` (counted against the `OPT_*` thresholds),
`vehicles_used`.

Given the same shipments, assignment tends to use *fewer* vehicles (consolidate)
and fleet balancing *more* (spread) — two useful answers to two different
operational questions.

---

## 4. Route optimization — `POST /optimize/routes`

Request (all optional): `warehouse_id`, `max_stops`, `strategy`.

```
Router: optimize_routes(payload)
  -> Service.optimize_routes(db, warehouse_id, max_stops, strategy)
       1. resolve the warehouse (given, or the one with the most routes)
       2. load the warehouse (as the start node) and its routes (as stops)
       3. route_optimizer.solve(warehouse, stops, strategy)  # nearest-neighbour
  -> RouteSolution -> RouteResponse (JSON)
```

Starting at the warehouse, nearest-neighbour repeatedly hops to the closest
unvisited stop. The response reports the **optimized** order and its distance,
the **naive** distance (stops in arrival order), and the **reduction**
(`distance_reduction_km`, `distance_reduction_percent`). Each `RouteStop`
carries its `sequence`, `leg_distance_km`, and running `cumulative_distance_km`.

Requesting `strategy: "vrp"` returns a clean `400` (reserved for a future week);
an unknown strategy also returns `400`.

---

## 5. Status — `GET /optimize/status`

No body. Returns the engine name, the installed OR-Tools version, the list of
solvers, the available route strategies, and the live settings. It does **not**
touch the database, so it stays a fast capability/liveness check (the optimizer
counterpart to Week 4's `/health`).

---

## Errors

Optimization errors flow through the **same** Week 4 exception handlers, so the
caller always sees the one JSON envelope `{ "error": { "code", "message" } }`:

| Situation | Status |
|-----------|--------|
| Unknown `warehouse_id` | `404` |
| Warehouse has no available vehicles / no routes | `400` |
| Reserved `vrp` strategy, or unknown strategy | `400` |
| Invalid body (e.g. `quantity` < 1, `sample_size` = 0) | `422` |

No optimization error ever leaks a stack trace or raw SQL.

---

## Trying it

```bash
uvicorn api.main:app --reload
# then, in another terminal or the Swagger UI at /docs:
curl -X POST http://127.0.0.1:8000/optimize/assignment -d '{"max_shipments": 40}' -H "Content-Type: application/json"
curl -X POST http://127.0.0.1:8000/optimize/fleet      -d '{"max_shipments": 40}' -H "Content-Type: application/json"
curl -X POST http://127.0.0.1:8000/optimize/warehouse  -d '{"sample_size": 15}'   -H "Content-Type: application/json"
curl -X POST http://127.0.0.1:8000/optimize/routes     -d '{"max_stops": 25}'     -H "Content-Type: application/json"

# or run the scripts (no server needed - they use the in-process TestClient):
python notebooks/week5_optimization_demo.py
python notebooks/week5_validation.py
```
