# Scenario Execution (Week 6)

The optimizer normally runs on the data as it is today. But planning teams must
also ask **"what if?"** — a holiday demand spike, half the vans breaking down, a
fuel-price jump, a supplier shipping late. A **scenario** is one such condition,
expressed as a small set of **changes applied to the optimizer's inputs** before
it solves. Nothing about the solver changes — only the numbers it is fed — so
**every scenario reuses the same Week 5 solvers unchanged**.

The code lives in `optimization/scenarios.py` (the catalog + the pure input
transforms) and is driven by the Week 6 execution service.

---

## The scenario catalog

| Key | Category | What it changes |
|-----|----------|-----------------|
| `normal` | baseline | nothing — the data as it is |
| `high_demand` | demand | package counts × 1.8 |
| `low_demand` | demand | package counts × 0.5 |
| `vehicle_breakdown` | resource | keep 50% of each warehouse's fleet |
| `warehouse_closed` | resource | mark one operating warehouse inactive **and** halve its fleet |
| `fuel_price_increase` | cost | every vehicle's per-km rate × 1.5 |
| `supplier_delay` | supply | tracked stock × 0.4 and demand × 1.2 |
| `priority_orders` | priority | keep only the highest-priority (largest) half of the shipments |
| `holiday` | demand | demand × 1.6, keep 80% of fleet, fuel × 1.1 |
| `demand_spike` | demand | package counts × 2.5 |
| `vehicle_failure` | resource | keep 50% of the fleet |

The first eight are the Week 6 core scenarios (Part 4). The last three are extra
scenarios the **benchmark runner** (Part 7) sweeps by default, alongside `normal`
and `supplier_delay`:

```
BENCHMARK_SCENARIOS = [normal, holiday, demand_spike, vehicle_failure, supplier_delay]
```

`GET /optimization/scenarios` returns this catalog as JSON.

---

## How a scenario is applied (pure transforms)

Each scenario is just a set of numeric **effects** (`ScenarioEffects`). The
functions in `scenarios.py` take the plain Week 5 input dataclasses and the stock
dictionary and return **modified copies** plus a human-readable list of what
changed — they never mutate the originals (`dataclasses.replace` makes copies)
and never touch the database.

```
ScenarioEffects
  demand_multiplier       ->  ShipmentInput.package_count  × m   (clamped to ≥ 1)
  vehicle_keep_fraction   ->  keep the first ⌊n·f⌋ vehicles per warehouse (≥ 1)
  fuel_multiplier         ->  VehicleInput.cost_per_km     × m
  stock_multiplier        ->  stock[(wh, product)]         × m   (floored)
  close_warehouses        ->  mark N active WarehouseInputs "inactive"
  priority_only           ->  keep the largest ⌈n/2⌉ shipments (highest priority)
```

The transforms are **deterministic** (no randomness): the same scenario on the
same data always produces the same modified inputs, so runs are reproducible —
the same discipline as the Week 2 simulation (fixed seed) and the Week 5
deterministic package-size hash.

---

## The execution flow

```
ExecutionService.run(optimizer, scenario, ...)
  1. LOAD the real inputs from the DB (shipments, vehicles, warehouses, stock)
  2. applied = apply_scenario(scenario, shipments, vehicles, warehouses, stock)
       -> applied.shipments / .vehicles / .warehouses / .stock  (modified copies)
       -> applied.changes                                       (what changed)
  3. SOLVE with the reused Week 5 solver on the modified inputs
  4. MEASURE + EVALUATE + (optionally) STORE
```

The `applied.changes` list is returned in the response (`scenario_changes`) and
stored in `optimization_runs.details`, so every run records exactly which
"what if" it faced.

---

## What each optimizer feels

Different scenarios bite different optimizers:

- **assignment / fleet** feel `demand_multiplier` (bigger loads → more vehicles,
  more stockouts, more at-risk-late), `vehicle_keep_fraction` (a smaller fleet
  must absorb the work), and `fuel_multiplier` (a costlier plan).
- **warehouse selection** feels `stock_multiplier` and `close_warehouses` (a
  supplier delay or a closure forces more demands to **pending**).
- **routing** is mostly distance-driven, so it mainly feels `priority_only`
  (fewer stops); demand/fuel/fleet changes do not alter the tour.

A scenario that leaves a warehouse with **no** vehicles returns a clean `400`
(nothing can be dispatched), never a crash.

---

## Benchmarking (Part 7)

`notebooks/week6_benchmark_runner.py` runs the **same** optimizer under every
`BENCHMARK_SCENARIOS` entry through `POST /optimization/run`, collects the KPIs,
and writes **one** report to `benchmarks/week6_benchmark_report.md` (and `.json`).
Because each run is persisted, the sweep also populates
`GET /optimization/history` and `GET /optimization/metrics`.

A representative run (optimizer = `assignment`, 50 shipments):

| Scenario | Cost | Veh. Util | Orders | Stockouts | Late |
|----------|------|-----------|--------|-----------|------|
| normal | 61206 | 75% | 50 | 0 | 24 |
| holiday | 38246 | 100% | 38 | 12 | 38 |
| demand_spike | 51902 | 100% | 38 | 12 | 38 |
| vehicle_failure | 54434 | 100% | 46 | 4 | 46 |
| supplier_delay | 61114 | 89% | 50 | 0 | 26 |

The story reads straight off the table: under a **holiday** or a **demand spike**
the fleet saturates (utilization pinned at 100%) and 12 orders become stockouts;
under a **vehicle failure** almost everything that *is* carried rides on stressed,
near-capacity vehicles (46 at-risk-of-late). This is exactly the kind of pressure
a planning team needs to see before it happens.

> Exact numbers vary with which warehouse is auto-selected and the shipment cap;
> the shape of the story is stable.
