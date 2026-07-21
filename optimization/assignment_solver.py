"""
============================================================================
SHIPMENT ASSIGNMENT SOLVER  (Week 5)
Project: Supply Chain & Logistics Optimizer
============================================================================

THE PROBLEM (in plain words)
----------------------------
  We have a pile of shipments waiting at warehouses and a fleet of vehicles.
  Decide which vehicle carries which shipment so that:
    - no vehicle is loaded past its package capacity   (a hard CONSTRAINT),
    - as many shipments as possible actually get carried,
    - and the vehicles we DO use are packed full - we "minimize unused
      capacity" by consolidating shipments onto as few vehicles as possible.

WHY THIS IS AN OPTIMIZATION PROBLEM (not just a loop)
-----------------------------------------------------
  Each shipment could go on any vehicle at its warehouse, so the number of
  possible plans explodes. Choosing capacity-respecting placements that also
  pack vehicles tightly is a classic INTEGER problem: every decision is a
  yes/no ("does shipment s ride on vehicle v?"). We hand that to OR-Tools'
  CP-SAT solver, which searches the huge space far better than a hand-written
  loop and can prove when a plan is optimal.

HOW WE MODEL IT FOR OR-TOOLS (CP-SAT)
-------------------------------------
  Variables : x[s, v] = 1 if shipment s travels on vehicle v, else 0.
              used[v] = 1 if vehicle v carries anything at all.
  Constraints:
     (1) each shipment rides on AT MOST one vehicle:   sum_v x[s,v] <= 1
     (2) capacity per vehicle: sum_s demand[s]*x[s,v] <= capacity[v]
     (3) link used[v] to the x's:  used[v] >= x[s,v]
  Objective : maximize  W * (packages carried)  -  (vehicles used)
              with W large enough that carrying one more package always beats
              opening one more vehicle. Carrying wins first; among equally-full
              plans, fewer vehicles wins (that is what shrinks unused capacity).

  We solve ONE warehouse at a time (a vehicle only carries its own warehouse's
  shipments). That keeps each model small and fast and mirrors reality - a van
  based at WH-0001 does not collect parcels sitting at WH-0050.

READY FOR THE FUTURE
--------------------
  All writes in the API go through the route service, so once a plan is chosen
  the assigned vehicle_id can be written into delivery_routes.vehicle_id (the
  nullable column Week 3 reserved) with no schema change.
============================================================================
"""

from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from optimization.config import OptimizationSettings, get_optimization_settings
from optimization.cost_functions import average_utilization, travel_cost
from optimization.solution_models import (
    AssignmentSolution,
    ShipmentAssignment,
    ShipmentInput,
    VehicleInput,
    VehicleLoad,
)
from optimization.utils import (
    BENCHMARK_MAX_DETERMINISTIC_TIME,
    BENCHMARK_RANDOM_SEED,
    BENCHMARK_WALL_BACKSTOP_SECONDS,
    Timer,
    as_percent,
    benchmark_deterministic_enabled,
    safe_divide,
)

# Human-readable names for the numeric status CP-SAT returns.
_CP_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


class AssignmentSolver:
    """
    Assign shipments to vehicles with OR-Tools CP-SAT, respecting capacity and
    minimizing unused capacity (by consolidating onto fewer vehicles).

    Construct once and call solve() as many times as you like. The solver holds
    no state between calls; it just carries the settings (time limit, etc.).
    """

    def __init__(self, settings: OptimizationSettings | None = None):
        self.settings = settings or get_optimization_settings()

    # -- public entry point --------------------------------------------------
    def solve(
        self,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
    ) -> AssignmentSolution:
        """
        Return an AssignmentSolution for the given shipments and vehicles.

        Shipments whose warehouse has no available vehicle are reported as
        unassigned (never silently dropped). Timing is measured around the whole
        solve so the caller can report execution_time_ms.
        """
        with Timer() as timer:
            solution = self._solve_inner(shipments, vehicles)
        solution.execution_time_ms = timer.elapsed_ms
        return solution

    # -- the work -------------------------------------------------------------
    def _solve_inner(
        self,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
    ) -> AssignmentSolution:
        if not shipments:
            return AssignmentSolution(
                success=True,
                status="OPTIMAL",
                message="No shipments to assign - nothing to do.",
            )

        # Group both sides by warehouse: a vehicle only serves its own site.
        ships_by_wh: dict[str | None, list[ShipmentInput]] = defaultdict(list)
        for s in shipments:
            ships_by_wh[s.warehouse_id].append(s)

        vehicles_by_wh: dict[str | None, list[VehicleInput]] = defaultdict(list)
        for v in vehicles:
            vehicles_by_wh[v.warehouse_id].append(v)

        all_assignments: list[ShipmentAssignment] = []
        all_loads: list[VehicleLoad] = []
        unassigned: list[str] = []
        worst_status = "OPTIMAL"

        # Solve each warehouse independently, then combine the results.
        for warehouse_id, wh_ships in ships_by_wh.items():
            wh_vehicles = vehicles_by_wh.get(warehouse_id, [])
            if not wh_vehicles:
                # No fleet here -> every shipment at this warehouse is unassigned.
                unassigned.extend(s.shipment_id for s in wh_ships)
                continue

            status, assignments, loads, wh_unassigned = self._solve_one_warehouse(
                warehouse_id, wh_ships, wh_vehicles
            )
            worst_status = self._merge_status(worst_status, status)
            all_assignments.extend(assignments)
            all_loads.extend(loads)
            unassigned.extend(wh_unassigned)

        return self._build_solution(
            worst_status, shipments, vehicles, all_assignments, all_loads, unassigned
        )

    def _solve_one_warehouse(
        self,
        warehouse_id: str | None,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
    ) -> tuple[str, list[ShipmentAssignment], list[VehicleLoad], list[str]]:
        """Build and solve the CP-SAT model for a single warehouse's fleet."""
        model = cp_model.CpModel()

        n_ships = len(shipments)
        n_vehicles = len(vehicles)
        demand = [max(0, int(s.package_count or 0)) for s in shipments]
        capacity = [max(0, int(v.capacity_packages or 0)) for v in vehicles]

        # x[s][v] = 1 if shipment s is carried by vehicle v.
        x = [
            [model.NewBoolVar(f"x_{s}_{v}") for v in range(n_vehicles)]
            for s in range(n_ships)
        ]
        # used[v] = 1 if vehicle v carries at least one shipment.
        used = [model.NewBoolVar(f"used_{v}") for v in range(n_vehicles)]

        # (1) each shipment is assigned to at most one vehicle.
        for s in range(n_ships):
            model.Add(sum(x[s][v] for v in range(n_vehicles)) <= 1)

        for v in range(n_vehicles):
            # (2) capacity: the packages loaded onto v may not exceed its limit.
            model.Add(
                sum(demand[s] * x[s][v] for s in range(n_ships)) <= capacity[v]
            )
            # (3) link used[v] to whether anything is loaded onto v.
            for s in range(n_ships):
                model.Add(used[v] >= x[s][v])

        # Objective: carry as many packages as possible first, then use as few
        # vehicles as possible (which is what minimizes total unused capacity).
        packages_carried = sum(
            demand[s] * x[s][v] for s in range(n_ships) for v in range(n_vehicles)
        )
        vehicles_opened = sum(used[v] for v in range(n_vehicles))
        weight = n_vehicles + 1  # one extra package must outweigh all vehicles.
        model.Maximize(weight * packages_carried - vehicles_opened)

        solver = self._make_solver()
        result = solver.Solve(model)
        status = _CP_STATUS_NAMES.get(result, "UNKNOWN")

        assignments: list[ShipmentAssignment] = []
        loads: list[VehicleLoad] = []
        unassigned: list[str] = []

        if result not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Could not place anything here; report all as unassigned.
            return status, assignments, loads, [s.shipment_id for s in shipments]

        # Read the chosen plan back out of the solver.
        loaded_packages = [0] * n_vehicles
        loaded_ships = [0] * n_vehicles
        for s in range(n_ships):
            placed = False
            for v in range(n_vehicles):
                if solver.Value(x[s][v]) == 1:
                    assignments.append(
                        ShipmentAssignment(
                            shipment_id=shipments[s].shipment_id,
                            vehicle_id=vehicles[v].vehicle_id,
                            warehouse_id=warehouse_id,
                            package_count=demand[s],
                        )
                    )
                    loaded_packages[v] += demand[s]
                    loaded_ships[v] += 1
                    placed = True
                    break
            if not placed:
                unassigned.append(shipments[s].shipment_id)

        for v in range(n_vehicles):
            loads.append(
                self._make_load(vehicles[v], loaded_packages[v], loaded_ships[v])
            )
        return status, assignments, loads, unassigned

    # -- helpers --------------------------------------------------------------
    def _make_solver(self) -> cp_model.CpSolver:
        """A CP-SAT solver configured from the optimization settings.

        A fixed random seed is always set (harmless, and it removes one source
        of run-to-run drift). In reproducible-benchmark mode
        (BENCHMARK_DETERMINISTIC) we force a SINGLE search worker and stop on
        DETERMINISTIC time (not wall-clock), which is what makes the chosen plan
        - and therefore every business KPI - identical across repeated runs and
        across machines, even for a hard instance that cannot be proven optimal.
        Production requests are untouched: they keep their many workers and the
        existing wall-clock time limit.
        """
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = BENCHMARK_RANDOM_SEED
        if benchmark_deterministic_enabled():
            solver.parameters.num_search_workers = 1
            solver.parameters.max_deterministic_time = BENCHMARK_MAX_DETERMINISTIC_TIME
            # Non-binding wall-clock backstop; the deterministic limit stops the
            # search first, so the result does not depend on machine speed.
            solver.parameters.max_time_in_seconds = max(
                self.settings.solver_time_limit_seconds, BENCHMARK_WALL_BACKSTOP_SECONDS
            )
        else:
            solver.parameters.max_time_in_seconds = self.settings.solver_time_limit_seconds
            if self.settings.solver_workers > 0:
                solver.parameters.num_search_workers = self.settings.solver_workers
        return solver

    def _make_load(
        self, vehicle: VehicleInput, loaded_packages: int, loaded_ships: int
    ) -> VehicleLoad:
        """Turn a vehicle's raw loaded totals into a VehicleLoad with metrics."""
        capacity = max(0, int(vehicle.capacity_packages or 0))
        utilization = safe_divide(loaded_packages, capacity, default=0.0)
        return VehicleLoad(
            vehicle_id=vehicle.vehicle_id,
            warehouse_id=vehicle.warehouse_id,
            capacity_packages=capacity,
            assigned_packages=loaded_packages,
            assigned_shipments=loaded_ships,
            utilization=round(utilization, 4),
            unused_capacity=max(0, capacity - loaded_packages),
            is_overloaded=utilization > self.settings.overloaded_utilization,
            is_underutilized=(
                loaded_ships > 0
                and utilization < self.settings.underutilized_utilization
            ),
        )

    @staticmethod
    def _merge_status(current: str, incoming: str) -> str:
        """
        Combine per-warehouse statuses into one overall status: if any sub-solve
        was merely FEASIBLE (not proven optimal) or failed, the overall result
        reflects the weaker outcome.
        """
        order = {"OPTIMAL": 0, "FEASIBLE": 1, "UNKNOWN": 2, "INFEASIBLE": 3, "MODEL_INVALID": 4}
        return current if order.get(current, 2) >= order.get(incoming, 2) else incoming

    def _build_solution(
        self,
        status: str,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
        assignments: list[ShipmentAssignment],
        loads: list[VehicleLoad],
        unassigned: list[str],
    ) -> AssignmentSolution:
        """Assemble the final solution object and its summary metrics."""
        # Price the plan: each assigned shipment's leg distance * its vehicle's
        # per-km cost. We look the vehicle rate up by id.
        cost_by_vehicle = {v.vehicle_id: v.cost_per_km for v in vehicles}
        distance_by_ship = {s.shipment_id: (s.distance_km or 0.0) for s in shipments}

        total_distance = 0.0
        total_cost = 0.0
        for a in assignments:
            leg = distance_by_ship.get(a.shipment_id, 0.0)
            total_distance += leg
            total_cost += travel_cost(leg, cost_by_vehicle.get(a.vehicle_id))

        vehicles_used = sum(1 for load in loads if load.assigned_shipments > 0)
        avg_util = average_utilization(loads)

        success = status in ("OPTIMAL", "FEASIBLE")
        message = (
            f"Assigned {len(assignments)} of {len(shipments)} shipments across "
            f"{vehicles_used} vehicle(s); average utilization "
            f"{as_percent(avg_util)}%."
        )
        return AssignmentSolution(
            success=success,
            status=status,
            assignments=assignments,
            vehicle_loads=loads,
            unassigned_shipments=unassigned,
            total_cost=round(total_cost, 2),
            total_distance_km=round(total_distance, 2),
            average_vehicle_utilization=round(avg_util, 4),
            vehicles_used=vehicles_used,
            constraint_violations=0,  # CP-SAT never returns a capacity breach.
            message=message,
        )


# A ready-to-use instance for the common case (default settings).
assignment_solver = AssignmentSolver()
