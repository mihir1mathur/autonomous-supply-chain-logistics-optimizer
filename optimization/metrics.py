"""
============================================================================
PERFORMANCE METRICS  (Week 6)   -- the KPIs of an optimization run
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT A "METRIC" (KPI) IS (zero-knowledge version)
-------------------------------------------------
  After the optimizer chooses a plan, we want to SCORE that plan with a handful
  of clear numbers a human can read at a glance: how much did it cost, how far
  do the vehicles drive, how full are they, how many orders got fulfilled, how
  many could not, how long did the solve take. Those numbers are the KEY
  PERFORMANCE INDICATORS (KPIs) of the run. This file turns a solver's output
  (the Solution dataclasses from Week 5) into ONE tidy RunMetrics object.

THE TWELVE METRICS THE WEEK 6 GOALS ASK FOR
-------------------------------------------
  1.  Total Cost            - money the plan spends (distance x per-km rate)
  2.  Travel Distance       - total kilometres driven
  3.  Vehicle Utilization   - how full the used vehicles are (0..1)
  4.  Warehouse Utilization - how full the source warehouse is (0..1)
  5.  Inventory Holding Cost- cost of the stock sitting on hand
  6.  Stockouts             - demands/shipments that could NOT be served
  7.  Late Deliveries       - deliveries at risk of being late (a proxy)
  8.  Orders Fulfilled      - deliveries the plan DID place
  9.  Optimization Runtime  - milliseconds the solve took
  10. Solver Status         - OPTIMAL / FEASIBLE / OK
  11. Number of Constraints - size of the model the solver reasoned about
  12. Number of Variables   - size of the model the solver reasoned about

WHY THIS FILE IS PURE (no database, no FastAPI, no OR-Tools)
------------------------------------------------------------
  Exactly like cost_functions.py and constraints.py in Week 5, everything here
  is a pure function of plain data: give it a Solution (and a little context)
  and it returns a RunMetrics. That keeps "how do we score a plan?" separate
  from "how do we solve?" and "how do we store?", and it makes every metric
  trivially unit-testable. The Week 6 execution service supplies the context
  (the source warehouse's utilization, the stock on hand) that the engine's
  Solution objects do not carry.

A NOTE ON "NUMBER OF VARIABLES / CONSTRAINTS" (an honest estimate)
------------------------------------------------------------------
  The Week 5 solvers do not report their raw model size back (and we do not
  modify them - Week 6 is additive). So we ESTIMATE the model size from the
  problem's dimensions using the exact structure each solver builds (see
  assignment_solver.py / vehicle_optimizer.py). For the greedy warehouse
  selector and the nearest-neighbour router - which are heuristics, not solver
  models - we report the number of DECISIONS made instead, and say so. These
  are labelled estimates, never presented as a solver's internal count.
============================================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from optimization.cost_functions import travel_cost
from optimization.execution_config import ExecutionSettings, get_execution_settings
from optimization.solution_models import (
    AssignmentSolution,
    FleetUtilizationSolution,
    RouteSolution,
    ShipmentAssignment,
    ShipmentInput,
    VehicleInput,
    VehicleLoad,
    WarehouseInput,
    WarehouseSelectionSolution,
)
from optimization.utils import safe_divide


# ===========================================================================
# THE UNIFIED METRICS OBJECT
# ===========================================================================
@dataclass
class RunMetrics:
    """
    The twelve KPIs of a single optimization run, in one tidy object.

    Every optimizer produces the SAME shape so runs are directly comparable and
    easy to store. A field that does not apply to a particular optimizer is left
    at its neutral default (0 / None) - e.g. a route optimization has no
    "stockouts", a warehouse selection has no "vehicle utilization".
    """

    # 1-2: cost and distance.
    total_cost: float = 0.0
    travel_distance_km: float = 0.0
    # 3-4: how full the fleet and the warehouse are (0..1 fractions).
    vehicle_utilization: float = 0.0
    warehouse_utilization: float = 0.0
    # 5: cost of stock sitting on hand.
    inventory_holding_cost: float = 0.0
    # 6-8: service outcomes.
    stockouts: int = 0
    late_deliveries: int = 0
    orders_fulfilled: int = 0
    # 9-10: how the solve went.
    optimization_runtime_ms: float = 0.0
    solver_status: str = "UNKNOWN"
    # 11-12: how big the model was (see the file header on estimation).
    num_constraints: int = 0
    num_variables: int = 0

    # A few extra descriptive fields (handy for reports; not one of the twelve).
    optimizer: str = ""                  # assignment / warehouse / fleet / routes
    vehicles_used: int = 0
    model_size_is_estimated: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


# ===========================================================================
# HELPERS shared by the assignment-style optimizers
# ===========================================================================
def _price_assignments(
    assignments: list[ShipmentAssignment],
    distance_by_shipment: dict[str, float],
    cost_per_km_by_vehicle: dict[str, float | None],
    default_cost_per_km: float,
) -> tuple[float, float]:
    """
    Return (total_distance_km, total_cost) for a list of assignments.

    Distance is the sum of each assigned shipment's leg (from Week 2's
    estimated_distance_km). Cost prices each leg at its vehicle's per-km rate,
    falling back to the configured default when a vehicle has no rate. This is
    the same pricing rule the Week 5 assignment solver uses; we reuse it here so
    the fleet optimizer (which does not compute cost itself) is priced the same.
    """
    total_distance = 0.0
    total_cost = 0.0
    for a in assignments:
        leg = distance_by_shipment.get(a.shipment_id, 0.0) or 0.0
        rate = cost_per_km_by_vehicle.get(a.vehicle_id)
        if rate is None:
            rate = default_cost_per_km
        total_distance += leg
        total_cost += travel_cost(leg, rate)
    return round(total_distance, 2), round(total_cost, 2)


def _count_late(
    assignments: list[ShipmentAssignment],
    loads: list[VehicleLoad],
    threshold: float,
) -> int:
    """
    Count deliveries "at risk of being late": those carried on a vehicle loaded
    above `threshold` of its capacity. See the file header - this is a
    documented PROXY, because the project has no live delivery clock. A stressed,
    over-full vehicle is the operational signal we use for lateness.
    """
    stressed = {ln.vehicle_id for ln in loads if ln.utilization > threshold}
    return sum(1 for a in assignments if a.vehicle_id in stressed)


def _avg_used_utilization(loads: list[VehicleLoad]) -> float:
    """Average utilization across vehicles that actually carried something."""
    used = [ln.utilization for ln in loads if ln.assigned_shipments > 0]
    return round(safe_divide(sum(used), len(used), default=0.0), 4)


def _estimate_assignment_model(n_ships: int, n_vehicles: int, *, has_peak: bool) -> tuple[int, int]:
    """
    Estimate (num_constraints, num_variables) for the CP-SAT assignment / fleet
    model, mirroring the structure the Week 5 solvers actually build:

      variables : x[s][v] (n_ships*n_vehicles) + one per-vehicle marker
                  (used[v] for assignment, or assigned[s] for fleet) + an
                  optional single `peak` variable (fleet only).
      constraints: one "each shipment <= 1 / == assigned" per shipment
                  (n_ships) + one capacity per vehicle (n_vehicles) + the
                  linking constraints (n_ships*n_vehicles for assignment's
                  used-link; n_vehicles for fleet's peak-link).

    These are honest structural estimates, not a solver read-out (the Week 5
    solvers are not modified). Good enough to show how model size scales.
    """
    cross = n_ships * n_vehicles
    if has_peak:  # fleet optimizer
        variables = cross + n_ships + 1              # x + assigned[s] + peak
        constraints = n_ships + n_vehicles + n_vehicles
    else:         # assignment optimizer
        variables = cross + n_vehicles               # x + used[v]
        constraints = n_ships + n_vehicles + cross
    return constraints, variables


# ===========================================================================
# RAW-PLAN METRICS  -- score any (assignments, loads, unassigned) plan
# ===========================================================================
def metrics_from_plan(
    optimizer: str,
    assignments: list[ShipmentAssignment],
    vehicle_loads: list[VehicleLoad],
    unassigned: list[str],
    *,
    status: str,
    runtime_ms: float,
    distance_by_shipment: dict[str, float],
    cost_per_km_by_vehicle: dict[str, float | None],
    warehouse_utilization: float = 0.0,
    inventory_holding_cost: float = 0.0,
    has_peak: bool = False,
    settings: ExecutionSettings | None = None,
) -> RunMetrics:
    """
    Score a plan given as raw pieces (assignments + per-vehicle loads + the
    shipments that were not placed), pricing it exactly like the solvers do.

    This is what lets the EVALUATION framework score its un-optimized "before"
    baseline (evaluation.naive_assignment) with the SAME rules the optimized
    "after" plan is scored by - an apples-to-apples comparison. The solver-backed
    wrappers below (metrics_from_assignment / metrics_from_fleet) share this
    shape; they simply trust the fields the solver already computed.
    """
    s = settings or get_execution_settings()
    n_ships = len(assignments) + len(unassigned)
    n_vehicles = len(vehicle_loads)
    constraints, variables = _estimate_assignment_model(n_ships, n_vehicles, has_peak=has_peak)
    distance, cost = _price_assignments(
        assignments, distance_by_shipment, cost_per_km_by_vehicle, s.default_cost_per_km
    )
    return RunMetrics(
        optimizer=optimizer,
        total_cost=cost,
        travel_distance_km=distance,
        vehicle_utilization=_avg_used_utilization(vehicle_loads),
        warehouse_utilization=round(warehouse_utilization or 0.0, 4),
        inventory_holding_cost=round(inventory_holding_cost, 2),
        stockouts=len(unassigned),
        late_deliveries=_count_late(assignments, vehicle_loads, s.late_delivery_load_threshold),
        orders_fulfilled=len(assignments),
        optimization_runtime_ms=runtime_ms,
        solver_status=status,
        num_constraints=constraints,
        num_variables=variables,
        vehicles_used=sum(1 for ln in vehicle_loads if ln.assigned_shipments > 0),
        model_size_is_estimated=True,
    )


# ===========================================================================
# 1) ASSIGNMENT  and  3) FLEET  (they share a shape)
# ===========================================================================
def metrics_from_assignment(
    solution: AssignmentSolution,
    *,
    distance_by_shipment: dict[str, float],
    cost_per_km_by_vehicle: dict[str, float | None],
    warehouse_utilization: float = 0.0,
    inventory_holding_cost: float = 0.0,
    settings: ExecutionSettings | None = None,
) -> RunMetrics:
    """KPIs for a SHIPMENT ASSIGNMENT solution (consolidate onto fewer vehicles)."""
    s = settings or get_execution_settings()
    n_ships = len(solution.assignments) + len(solution.unassigned_shipments)
    n_vehicles = len(solution.vehicle_loads)
    constraints, variables = _estimate_assignment_model(n_ships, n_vehicles, has_peak=False)

    # The Week 5 assignment solution already carries cost/distance; trust it.
    return RunMetrics(
        optimizer="assignment",
        total_cost=solution.total_cost,
        travel_distance_km=solution.total_distance_km,
        vehicle_utilization=solution.average_vehicle_utilization,
        warehouse_utilization=round(warehouse_utilization or 0.0, 4),
        inventory_holding_cost=round(inventory_holding_cost, 2),
        stockouts=len(solution.unassigned_shipments),
        late_deliveries=_count_late(
            solution.assignments, solution.vehicle_loads, s.late_delivery_load_threshold
        ),
        orders_fulfilled=len(solution.assignments),
        optimization_runtime_ms=solution.execution_time_ms,
        solver_status=solution.status,
        num_constraints=constraints,
        num_variables=variables,
        vehicles_used=solution.vehicles_used,
        model_size_is_estimated=True,
    )


def metrics_from_fleet(
    solution: FleetUtilizationSolution,
    *,
    distance_by_shipment: dict[str, float],
    cost_per_km_by_vehicle: dict[str, float | None],
    warehouse_utilization: float = 0.0,
    inventory_holding_cost: float = 0.0,
    settings: ExecutionSettings | None = None,
) -> RunMetrics:
    """
    KPIs for a VEHICLE UTILIZATION (fleet balancing) solution.

    The fleet solution does not compute cost/distance itself (its job is
    balance, not price), so we price it here from the assignments using the same
    rule as assignment - which also makes the two directly comparable.
    """
    s = settings or get_execution_settings()
    n_ships = len(solution.assignments) + len(solution.unassigned_shipments)
    n_vehicles = len(solution.vehicle_loads)
    constraints, variables = _estimate_assignment_model(n_ships, n_vehicles, has_peak=True)

    distance, cost = _price_assignments(
        solution.assignments, distance_by_shipment, cost_per_km_by_vehicle, s.default_cost_per_km
    )
    return RunMetrics(
        optimizer="fleet",
        total_cost=cost,
        travel_distance_km=distance,
        vehicle_utilization=solution.average_utilization,
        warehouse_utilization=round(warehouse_utilization or 0.0, 4),
        inventory_holding_cost=round(inventory_holding_cost, 2),
        stockouts=len(solution.unassigned_shipments),
        late_deliveries=_count_late(
            solution.assignments, solution.vehicle_loads, s.late_delivery_load_threshold
        ),
        orders_fulfilled=len(solution.assignments),
        optimization_runtime_ms=solution.execution_time_ms,
        solver_status=solution.status,
        num_constraints=constraints,
        num_variables=variables,
        vehicles_used=solution.vehicles_used,
        model_size_is_estimated=True,
    )


# ===========================================================================
# 2) WAREHOUSE SELECTION
# ===========================================================================
def metrics_from_warehouse(
    solution: WarehouseSelectionSolution,
    *,
    warehouse_utilization: float = 0.0,
    inventory_holding_cost: float = 0.0,
    settings: ExecutionSettings | None = None,
) -> RunMetrics:
    """
    KPIs for a WAREHOUSE SELECTION solution (nearest in-stock warehouse each).

    Cost is the total selection distance priced at the default per-km rate
    (there is no vehicle here). "Stockouts" are the pending demands - the ones
    no operating warehouse could serve. The greedy selector is not a solver
    model, so num_variables/num_constraints report the DECISION count (one per
    demand), and model_size_is_estimated stays False to signal "not a model".
    """
    s = settings or get_execution_settings()
    n_decisions = solution.assigned_count + solution.pending_count
    return RunMetrics(
        optimizer="warehouse",
        total_cost=round(solution.total_distance_km * s.default_cost_per_km, 2),
        travel_distance_km=solution.total_distance_km,
        vehicle_utilization=0.0,  # no vehicles in warehouse selection.
        warehouse_utilization=round(warehouse_utilization or 0.0, 4),
        inventory_holding_cost=round(inventory_holding_cost, 2),
        stockouts=solution.pending_count,
        late_deliveries=0,
        orders_fulfilled=solution.assigned_count,
        optimization_runtime_ms=solution.execution_time_ms,
        solver_status=solution.status,
        num_constraints=n_decisions,   # decisions considered (greedy heuristic).
        num_variables=n_decisions,
        vehicles_used=0,
        model_size_is_estimated=False,
    )


# ===========================================================================
# 4) ROUTE OPTIMIZATION
# ===========================================================================
def metrics_from_route(
    solution: RouteSolution,
    *,
    warehouse_utilization: float = 0.0,
    inventory_holding_cost: float = 0.0,
    settings: ExecutionSettings | None = None,
) -> RunMetrics:
    """
    KPIs for a ROUTE OPTIMIZATION solution (order one warehouse's stops).

    Cost is the optimized distance priced at the default per-km rate. Orders
    fulfilled is the number of stops on the route. Nearest-neighbour is a
    heuristic, not a solver model, so the size fields report the stop count.
    """
    s = settings or get_execution_settings()
    return RunMetrics(
        optimizer="routes",
        total_cost=round(solution.total_distance_km * s.default_cost_per_km, 2),
        travel_distance_km=solution.total_distance_km,
        vehicle_utilization=0.0,
        warehouse_utilization=round(warehouse_utilization or 0.0, 4),
        inventory_holding_cost=round(inventory_holding_cost, 2),
        stockouts=0,
        late_deliveries=0,
        orders_fulfilled=solution.stop_count,
        optimization_runtime_ms=solution.execution_time_ms,
        solver_status=solution.status,
        num_constraints=solution.stop_count,   # decisions considered (heuristic).
        num_variables=solution.stop_count,
        vehicles_used=1 if solution.stop_count > 0 else 0,
        model_size_is_estimated=False,
    )


# ===========================================================================
# INVENTORY HOLDING COST  (a small pure helper the service reuses)
# ===========================================================================
def inventory_holding_cost(
    stock_units_on_hand: int,
    settings: ExecutionSettings | None = None,
) -> float:
    """
    Price the stock sitting on hand: units * the per-unit holding rate.

    A simulated accounting figure (Olist has none), documented in
    execution_config.py. The service passes the stock at the warehouse(s)
    involved in the run so this reflects the inventory the plan draws on.
    """
    s = settings or get_execution_settings()
    return round(max(0, stock_units_on_hand) * s.inventory_holding_cost_per_unit, 2)
