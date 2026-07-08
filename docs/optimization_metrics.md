# Optimization Metrics (Week 6)

After the optimizer chooses a plan, the execution layer scores it with a fixed
set of **key performance indicators (KPIs)** — clear numbers a human can read at
a glance and a database can store and compare. This document lists the twelve
metrics, how each is computed, and where the numbers come from.

The code lives in `optimization/metrics.py`. It is **pure**: every function is a
plain function of the Week 5 solution dataclasses plus a little context (the
source warehouse's utilization, the stock on hand) that the service supplies —
no database, no FastAPI, no OR-Tools, exactly like `cost_functions.py` and
`constraints.py` in Week 5.

---

## The twelve KPIs

Every optimizer produces the **same** `RunMetrics` shape, so runs are directly
comparable and easy to store. A field that does not apply to a given optimizer is
left at its neutral default (`0` / `""`).

| # | Metric | Field | How it is computed |
|---|--------|-------|--------------------|
| 1 | Total Cost | `total_cost` | Σ (leg distance × the vehicle's `cost_per_km`); a default rate is used where there is no vehicle (routes, warehouse). |
| 2 | Travel Distance | `travel_distance_km` | Σ of the assigned legs' `estimated_distance_km` (Week 2), or the route's optimized distance. |
| 3 | Vehicle Utilization | `vehicle_utilization` | Average `assigned_packages / capacity` over the vehicles that carried something (0..1). |
| 4 | Warehouse Utilization | `warehouse_utilization` | The source warehouse's `current_utilization` (Week 2), 0..1. |
| 5 | Inventory Holding Cost | `inventory_holding_cost` | Units of stock on hand × a per-unit holding rate (simulated). |
| 6 | Stockouts | `stockouts` | Shipments that could not be placed (no capacity) or demands that no warehouse could serve (pending). |
| 7 | Late Deliveries | `late_deliveries` | Deliveries carried on a vehicle loaded above the late-delivery threshold (a documented **proxy**). |
| 8 | Orders Fulfilled | `orders_fulfilled` | Shipments assigned / demands placed / stops routed. |
| 9 | Optimization Runtime | `optimization_runtime_ms` | Wall-clock time of the solve (`Timer`, Week 5). |
| 10 | Solver Status | `solver_status` | `OPTIMAL` / `FEASIBLE` (CP-SAT) or `OK` (heuristics). |
| 11 | Number of Constraints | `num_constraints` | Estimated from the model's structure (see below). |
| 12 | Number of Variables | `num_variables` | Estimated from the model's structure (see below). |

Two extra descriptive fields ride along: `optimizer` (which problem produced the
run) and `vehicles_used`.

---

## Where each number comes from, by optimizer

```
assignment  cost/distance/util : taken straight from AssignmentSolution (Week 5)
            stockouts          : len(unassigned_shipments)
            late               : shipments on vehicles with utilization > 0.90
            orders             : len(assignments)

fleet       cost/distance      : PRICED here from the assignments (the fleet
                                 solver optimises balance, not price, so it does
                                 not compute cost itself) - same rule as assignment
            util               : average_utilization (FleetUtilizationSolution)

warehouse   distance           : total selection distance (nearest feasible)
            cost               : distance × default per-km rate (no vehicle here)
            stockouts          : pending_count (no warehouse had stock)
            orders             : assigned_count

routes      distance           : the optimized (nearest-neighbour) distance
            cost               : distance × default per-km rate
            orders             : stop_count
```

---

## The two simulated costs (documented honesty)

The Olist data has **no accounting figures**, so two rates are *simulated*
assumptions, defined once in `optimization/execution_config.py` and clearly
labelled — the same real-vs-simulated discipline as Week 2:

- **`OPT_DEFAULT_COST_PER_KM`** (default `1.20`) — the per-km rate used to price a
  plan that has no vehicle rate. `1.20` matches the rate Week 2 used to compute
  `delivery_routes.estimated_cost`, so the numbers line up with the stored data.
- **`OPT_INVENTORY_HOLDING_COST_PER_UNIT`** (default `0.10`) — the cost of holding
  one unit of stock for the reporting period. Inventory holding cost =
  units on hand × this rate.

---

## The late-delivery proxy

This project has **no live delivery clock**, so "late deliveries" is a documented
**proxy**: a shipment carried on a vehicle loaded above
`OPT_LATE_DELIVERY_LOAD_THRESHOLD` (default `0.90`, the same fraction Week 5 calls
"overloaded") is flagged *at risk of being late*. A stressed, over-full vehicle
is the operational signal we use. Under a demand spike or a vehicle failure the
remaining vehicles run near capacity, so this count rises — exactly the pressure
those scenarios model.

---

## "Number of variables / constraints" is an honest estimate

The Week 5 solvers do not report their raw model size back, and Week 6 does not
modify them. So the CP-SAT problems (assignment, fleet) have their size
**estimated from the problem's dimensions**, mirroring the exact structure each
solver builds:

```
assignment  variables  ≈ shipments × vehicles  +  vehicles          (x[s][v] + used[v])
            constraints ≈ shipments + vehicles + shipments × vehicles
fleet       variables  ≈ shipments × vehicles  +  shipments  +  1   (x + assigned[s] + peak)
            constraints ≈ shipments + 2 × vehicles
```

`model_size_is_estimated` is `True` for these. For the **greedy** warehouse
selector and the **nearest-neighbour** router — which are heuristics, not solver
models — the size fields report the number of *decisions* made and
`model_size_is_estimated` is `False`, so a reader can tell the difference.

---

## Storage

Each run's KPIs are **promoted to real columns** on the `optimization_runs`
table, so `GET /optimization/history` can sort by them and
`GET /optimization/metrics` can aggregate them directly, while the complete
`RunMetrics` object is also kept as a JSON blob for full detail. See
[`optimization_execution.md`](optimization_execution.md).

---

## Example (real numbers)

An `assignment` run under `high_demand` on the busiest warehouse, 40 shipments:

```
total cost             : 47680.91
travel distance (km)   : 39884.33
vehicle utilization    : 91.5%
warehouse utilization  : (the warehouse's current_utilization)
inventory holding cost : (stock on hand × 0.10)
stockouts              : 0
late deliveries        : 20     (demand 1.8x pushes vehicles near capacity)
orders fulfilled       : 40
runtime (ms)           : ~130
solver status          : OPTIMAL
variables / constraints: 164 / 204   (estimated)
```
