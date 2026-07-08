# Evaluation Framework (Week 6)

Running an optimizer and printing its numbers does not, by itself, prove the
optimizer **helped**. To show that, we need something to compare against: what
would the same situation have cost *without* optimization? The evaluation
framework builds that "before" picture, compares it to the optimizer's "after"
plan, and reports the improvement as clear percentages.

The code lives in `optimization/evaluation.py`. Like `metrics.py`, it is **pure**
— plain functions over the Week 5 dataclasses, no database and no web — so "did
it improve, and by how much?" is reusable and unit-testable.

---

## The two pieces

```
1. BASELINES ("before")   deliberately un-clever plans the optimizer must beat
      naive_assignment            spread shipments round-robin, first-that-fits,
                                  with NO consolidation and NO balancing
      naive_warehouse_selection   serve each demand from the FIRST operating,
                                  in-stock warehouse found (IGNORE distance)
      (routing's baseline is built in: RouteSolution.naive_distance_km is the
       distance in arrival order, before nearest-neighbour reorders the stops)

2. COMPARISON             evaluate(before_metrics, after_metrics) -> EvaluationResult
      turns two RunMetrics into one block of improvement percentages
```

Both the "before" baseline and the "after" optimized plan are scored by the
**same** `metrics.py` functions (the baseline via `metrics_from_plan`), so the
comparison is strictly apples-to-apples.

---

## Direction: positive always means "better"

Some metrics improve by going **down** (cost, distance, holding cost, stockouts,
late deliveries); some improve by going **up** (utilization, orders fulfilled).
The framework computes a signed percentage for each so that a **positive number
always means the after-plan is better**, regardless of direction:

```
reduction_percent(before, after) = (before - after) / before × 100    # lower is better
increase_percent (before, after) = (after - before) / before × 100    # higher is better
```

A zero baseline is guarded (returns `0.0`, or `100.0` for "went from nothing to
something"), so an empty result never divides by zero.

---

## `EvaluationResult`

| Field | Meaning (positive = better) |
|-------|------------------------------|
| `cost_reduction_percent` | how much cheaper the optimized plan is |
| `distance_reduction_percent` | how much less distance it drives |
| `inventory_reduction_percent` | how much less stock it ties up |
| `stockout_reduction_percent` | how many fewer unfulfillable orders |
| `late_delivery_reduction_percent` | how many fewer at-risk deliveries |
| `utilization_improvement_percent` | how much fuller the used vehicles are |
| `delivery_improvement_percent` | how many more orders are fulfilled |
| `resource_utilization_percent` | the after-plan's vehicle utilization (absolute, 0..100) |
| `before`, `after` | the two full `RunMetrics` snapshots |
| `summary` | a one-line human-readable digest |

---

## The baselines in detail

**`naive_assignment`** — the "before" for the *assignment* and *fleet*
optimizers. It hands shipments to vehicles per warehouse in a round-robin,
first-that-fits way, respecting capacity but with **no** global objective. This
is roughly what assigning by hand looks like ("next parcel, next van"). The Week
5 assignment solver should use **fewer, fuller** vehicles than this; the fleet
solver should keep the loads **more even**.

**`naive_warehouse_selection`** — the "before" for the *warehouse* optimizer. It
serves each demand from the **first** operating, in-stock warehouse found in list
order, **ignoring distance**. The Week 5 selector picks the **nearest** feasible
one instead, so its total distance is shorter — that gap is the improvement.

**Routing** needs no separate baseline: `RouteSolution.naive_distance_km` already
reports the distance of visiting the stops in arrival order, which the
nearest-neighbour order is compared against.

---

## How the execution service uses it

For every run (unless `evaluate=false`), the execution service:

1. builds the "after" `RunMetrics` from the solver's solution;
2. builds a "before" `RunMetrics` from the matching baseline on the **same**
   (post-scenario) inputs;
3. calls `evaluate(before, after)` and attaches the result to the run and to the
   stored `optimization_runs.evaluation` JSON.

---

## Example (real numbers)

`assignment` under the `normal` scenario, 40 shipments, busiest warehouse:

```
before (naive round-robin): 4 vehicles used, ~60% average utilization
after  (CP-SAT consolidate): 2 vehicles used, ~76.7% average utilization

evaluate(before, after):
  cost reduction        +3.4%
  distance reduction    +0%     (all 40 shipments carried either way, so the
                                 total leg distance is unchanged)
  utilization           +27.5%  (now 76.7%)
  orders                +0%
```

The story is **consolidation**: the optimizer carries the same work on **half**
the vehicles at much higher utilization. For the *route* optimizer the headline
is instead a large **distance reduction** (~61% on a 25-stop route vs the naive
order); for the *warehouse* optimizer it is a **distance reduction** from serving
the nearest in-stock site rather than the first one found.

> Note: the *fleet* optimizer's job is **balance**, not cost — so it can show a
> small *negative* utilization change versus the naive baseline (it deliberately
> spreads load across more vehicles). That is expected and is why the summary
> prints signed values.
