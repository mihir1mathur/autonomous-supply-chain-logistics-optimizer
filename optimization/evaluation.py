"""
============================================================================
EVALUATION FRAMEWORK  (Week 6)   -- BEFORE optimization vs AFTER
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT "EVALUATION" MEANS HERE (zero-knowledge version)
-----------------------------------------------------
  It is not enough to run an optimizer and print its numbers. To PROVE the
  optimizer helped, we need something to compare against: what would the same
  situation have cost WITHOUT optimization? This file builds that "before"
  picture (a simple, un-optimized plan), then compares it to the optimizer's
  "after" plan and reports the improvement as clear percentages:

      cost reduction, distance reduction, delivery improvement,
      inventory improvement, and the resulting resource utilization.

TWO PIECES
----------
  1. BASELINES ("before") - small, deliberately un-clever plans:
       * naive_assignment  - spread shipments round-robin across the fleet,
                             with no attempt to consolidate or balance. This is
                             what a dispatcher does by hand: "next parcel, next
                             van". The Week 5 optimizers must beat it.
       * naive_warehouse   - serve each demand from the FIRST operating,
                             in-stock warehouse found (ignore distance). The
                             Week 5 selector picks the NEAREST instead.
       * (routing has its baseline built in: RouteSolution.naive_distance_km is
          the distance in arrival order, before nearest-neighbour reorders.)

  2. COMPARISON - evaluate(before_metrics, after_metrics) turns two RunMetrics
     into one EvaluationResult of percentage improvements.

WHY PURE FUNCTIONS (no database, no FastAPI, no OR-Tools)
---------------------------------------------------------
  Like metrics.py, everything here is a pure function of plain data. The Week 6
  execution service builds the "before" and "after" RunMetrics and hands them to
  evaluate(); this module never touches the database or the web. That makes the
  "did it improve, and by how much?" question reusable and unit-testable.

DIRECTION OF EACH METRIC (lower-is-better vs higher-is-better)
--------------------------------------------------------------
  Some metrics improve by going DOWN (cost, distance, holding cost, stockouts,
  late deliveries); some improve by going UP (utilization, orders fulfilled).
  We compute a signed "improvement percent" for each so a positive number
  ALWAYS means "better", regardless of direction.
============================================================================
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from optimization.constraints import can_warehouse_serve
from optimization.metrics import RunMetrics
from optimization.solution_models import (
    DemandInput,
    ShipmentAssignment,
    ShipmentInput,
    VehicleInput,
    VehicleLoad,
    WarehouseChoice,
    WarehouseInput,
    WarehouseSelectionSolution,
)
from optimization.utils import DEFAULT_WINDING_FACTOR, road_distance_km, safe_divide


# ===========================================================================
# PERCENTAGE MATH  (the two directions, made safe)
# ===========================================================================
def reduction_percent(before: float, after: float) -> float:
    """
    Percent DROP from before to after (for lower-is-better metrics like cost).
    Positive = improved (went down). Guards a zero baseline -> 0.0.
    """
    if not before:
        return 0.0
    return round((before - after) / before * 100.0, 1)


def increase_percent(before: float, after: float) -> float:
    """
    Percent RISE from before to after (for higher-is-better metrics like
    utilization or orders fulfilled). Positive = improved (went up).
    """
    if not before:
        # If we went from nothing to something, that is a full improvement.
        return 100.0 if after else 0.0
    return round((after - before) / before * 100.0, 1)


# ===========================================================================
# THE COMPARISON RESULT
# ===========================================================================
@dataclass
class EvaluationResult:
    """
    The improvement of an AFTER plan over a BEFORE baseline, as percentages
    (positive always means "better"), plus the raw before/after snapshots.
    """

    # lower-is-better metrics: positive percent = we spent/drove/wasted less.
    cost_reduction_percent: float = 0.0
    distance_reduction_percent: float = 0.0
    inventory_reduction_percent: float = 0.0
    stockout_reduction_percent: float = 0.0
    late_delivery_reduction_percent: float = 0.0
    # higher-is-better metrics: positive percent = we used/served more.
    utilization_improvement_percent: float = 0.0
    delivery_improvement_percent: float = 0.0
    # a convenient absolute read-out of the AFTER plan's resource use (0..100).
    resource_utilization_percent: float = 0.0

    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    summary: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate(before: RunMetrics, after: RunMetrics) -> EvaluationResult:
    """
    Compare a BEFORE baseline to an AFTER optimized plan and return the
    improvement percentages. Every "*_reduction_percent" and
    "*_improvement_percent" is positive when the AFTER plan is better.
    """
    result = EvaluationResult(
        cost_reduction_percent=reduction_percent(before.total_cost, after.total_cost),
        distance_reduction_percent=reduction_percent(
            before.travel_distance_km, after.travel_distance_km
        ),
        inventory_reduction_percent=reduction_percent(
            before.inventory_holding_cost, after.inventory_holding_cost
        ),
        stockout_reduction_percent=reduction_percent(before.stockouts, after.stockouts),
        late_delivery_reduction_percent=reduction_percent(
            before.late_deliveries, after.late_deliveries
        ),
        utilization_improvement_percent=increase_percent(
            before.vehicle_utilization, after.vehicle_utilization
        ),
        delivery_improvement_percent=increase_percent(
            before.orders_fulfilled, after.orders_fulfilled
        ),
        resource_utilization_percent=round(after.vehicle_utilization * 100.0, 1),
        before=before.as_dict(),
        after=after.as_dict(),
    )
    # Format with explicit signs so a negative value (a metric that got WORSE
    # than the baseline, e.g. fleet balancing deliberately spreads load and can
    # lower average utilization) reads cleanly, never as a double sign.
    result.summary = (
        f"cost reduction {result.cost_reduction_percent:+g}%, "
        f"distance reduction {result.distance_reduction_percent:+g}%, "
        f"utilization {result.utilization_improvement_percent:+g}% "
        f"(now {result.resource_utilization_percent}%), "
        f"orders {result.delivery_improvement_percent:+g}%."
    )
    return result


# ===========================================================================
# BASELINES  -- the un-optimized "before" plans
# ===========================================================================
def naive_assignment(
    shipments: list[ShipmentInput],
    vehicles: list[VehicleInput],
) -> tuple[list[ShipmentAssignment], list[VehicleLoad], list[str]]:
    """
    A deliberately un-clever "before" plan: hand shipments to vehicles in a
    ROUND-ROBIN, first-that-fits way, per warehouse, with NO consolidation and
    NO balancing. This is roughly what assigning by hand looks like.

    Returns the same (assignments, vehicle_loads, unassigned) shapes the Week 5
    solvers return, so metrics_from_* can score it identically to the optimized
    plan. The Week 5 assignment optimizer should use FEWER, fuller vehicles than
    this, and the fleet optimizer should keep the loads more even.
    """
    # Group both sides by warehouse (a vehicle only serves its own site), the
    # same way the Week 5 solvers do.
    ships_by_wh: dict[str | None, list[ShipmentInput]] = defaultdict(list)
    for s in shipments:
        ships_by_wh[s.warehouse_id].append(s)
    vehicles_by_wh: dict[str | None, list[VehicleInput]] = defaultdict(list)
    for v in vehicles:
        vehicles_by_wh[v.warehouse_id].append(v)

    assignments: list[ShipmentAssignment] = []
    unassigned: list[str] = []
    # Track how many packages each vehicle has taken so we never exceed capacity.
    loaded_pkgs: dict[str, int] = {v.vehicle_id: 0 for v in vehicles}
    loaded_ships: dict[str, int] = {v.vehicle_id: 0 for v in vehicles}

    for warehouse_id, wh_ships in ships_by_wh.items():
        wh_vehicles = vehicles_by_wh.get(warehouse_id, [])
        if not wh_vehicles:
            unassigned.extend(s.shipment_id for s in wh_ships)
            continue
        n_v = len(wh_vehicles)
        for i, s in enumerate(wh_ships):
            demand = max(0, int(s.package_count or 0))
            placed = False
            # Try vehicles starting from a round-robin offset, taking the first
            # that still has room (no global optimization anywhere here).
            for step in range(n_v):
                v = wh_vehicles[(i + step) % n_v]
                cap = max(0, int(v.capacity_packages or 0))
                if loaded_pkgs[v.vehicle_id] + demand <= cap:
                    assignments.append(
                        ShipmentAssignment(
                            shipment_id=s.shipment_id,
                            vehicle_id=v.vehicle_id,
                            warehouse_id=warehouse_id,
                            package_count=demand,
                        )
                    )
                    loaded_pkgs[v.vehicle_id] += demand
                    loaded_ships[v.vehicle_id] += 1
                    placed = True
                    break
            if not placed:
                unassigned.append(s.shipment_id)

    loads = [
        _naive_load(v, loaded_pkgs[v.vehicle_id], loaded_ships[v.vehicle_id])
        for v in vehicles
    ]
    return assignments, loads, unassigned


def naive_warehouse_selection(
    demands: list[DemandInput],
    warehouses: list[WarehouseInput],
    stock: dict[tuple[str, str], int],
    winding_factor: float = DEFAULT_WINDING_FACTOR,
) -> WarehouseSelectionSolution:
    """
    A deliberately un-clever "before" plan for warehouse selection: serve each
    demand from the FIRST operating, in-stock warehouse found in list order,
    IGNORING distance. (The Week 5 selector picks the NEAREST feasible one, so
    its total distance should be shorter - that difference is the improvement.)

    Returns the same WarehouseSelectionSolution shape as the real selector so
    metrics_from_warehouse can score it identically.
    """
    remaining = dict(stock)
    choices: list[WarehouseChoice] = []
    assigned = 0
    pending = 0
    total_distance = 0.0

    for demand in demands:
        chosen = None
        for wh in warehouses:  # FIRST feasible, not nearest.
            have = remaining.get((wh.warehouse_id, demand.product_id), 0)
            if can_warehouse_serve(wh, demand, have):
                chosen = wh
                break
        if chosen is None:
            choices.append(
                WarehouseChoice(
                    demand_id=demand.demand_id,
                    product_id=demand.product_id,
                    quantity=demand.quantity,
                    selected_warehouse_id=None,
                    distance_km=0.0,
                    status="pending",
                    reason="No operating warehouse holds enough stock (baseline).",
                )
            )
            pending += 1
            continue
        remaining[(chosen.warehouse_id, demand.product_id)] = (
            remaining.get((chosen.warehouse_id, demand.product_id), 0) - demand.quantity
        )
        distance = road_distance_km(
            chosen.latitude, chosen.longitude,
            demand.destination_latitude, demand.destination_longitude,
            winding_factor,
        )
        choices.append(
            WarehouseChoice(
                demand_id=demand.demand_id,
                product_id=demand.product_id,
                quantity=demand.quantity,
                selected_warehouse_id=chosen.warehouse_id,
                distance_km=round(distance, 2),
                status="assigned",
                reason="First operating warehouse with stock (baseline, ignores distance).",
            )
        )
        assigned += 1
        total_distance += distance

    avg = safe_divide(total_distance, assigned, default=0.0)
    return WarehouseSelectionSolution(
        success=True,
        status="BASELINE",
        choices=choices,
        assigned_count=assigned,
        pending_count=pending,
        average_distance_km=round(avg, 2),
        total_distance_km=round(total_distance, 2),
        message=f"Baseline first-feasible selection: {assigned} assigned, {pending} pending.",
    )


def _naive_load(vehicle: VehicleInput, pkgs: int, ships: int) -> VehicleLoad:
    """Turn a naive vehicle's raw totals into a VehicleLoad (same as Week 5)."""
    cap = max(0, int(vehicle.capacity_packages or 0))
    util = safe_divide(pkgs, cap, default=0.0)
    return VehicleLoad(
        vehicle_id=vehicle.vehicle_id,
        warehouse_id=vehicle.warehouse_id,
        capacity_packages=cap,
        assigned_packages=pkgs,
        assigned_shipments=ships,
        utilization=round(util, 4),
        unused_capacity=max(0, cap - pkgs),
        is_overloaded=False,
        is_underutilized=False,
    )
