"""
============================================================================
VEHICLE UTILIZATION OPTIMIZER  (Week 5)
Project: Supply Chain & Logistics Optimizer
============================================================================

THE PROBLEM (in plain words)
----------------------------
  The assignment solver packs shipments onto as FEW vehicles as possible.
  Sometimes we want the opposite emphasis: spread the work EVENLY so no single
  vehicle is slammed to the brim while others sit nearly empty. Even loading
  reduces wear, keeps a safety margin on every vehicle, and avoids one late
  van holding up the day. This solver BALANCES the fleet.

WHAT "BALANCED" MEANS HERE
--------------------------
  We minimize the PEAK utilization - the fullest vehicle's load as a fraction
  of its capacity. Pushing the worst case down naturally pulls the fleet
  together: if the busiest van can be less full, the solver must have shifted
  some of its load to an emptier one. We still respect every capacity limit and
  still try to carry every shipment.

HOW WE MODEL IT FOR OR-TOOLS (CP-SAT)
-------------------------------------
  Variables : x[s, v] = 1 if shipment s is on vehicle v.
              peak    = an integer in 0..1000 standing for the highest
                        utilization reached, in PER-MILLE (so 750 = 75.0%).
  Constraints:
     (1) each shipment goes on at most one vehicle.
     (2) capacity per vehicle:  load[v] <= capacity[v].
     (3) peak links to every vehicle:  load[v] * 1000 <= peak * capacity[v].
         (This says "peak is at least as big as every vehicle's utilization".)
  Objective : minimize  BIG * (packages left unassigned)  +  peak.
              Carrying shipments dominates (BIG is huge), and among plans that
              carry the same amount, the one with the lowest peak - the most
              balanced - wins.

WHY INTEGERS / PER-MILLE
------------------------
  CP-SAT works in integers, and utilization is a fraction. Multiplying through
  by 1000 turns "load/capacity <= peak" into the integer inequality above with
  no division, which CP-SAT handles cleanly.

CONTRAST WITH THE ASSIGNMENT SOLVER
-----------------------------------
  Same variables and capacity rule; DIFFERENT objective. Assignment minimizes
  vehicles used (consolidate); this minimizes the peak load (spread). Two views
  of the same fleet, each exposed as its own endpoint.
============================================================================
"""

from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from optimization.config import OptimizationSettings, get_optimization_settings
from optimization.solution_models import (
    FleetUtilizationSolution,
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

_PER_MILLE = 1000  # utilization scaled to integers: 1000 = 100%.

_CP_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


class VehicleOptimizer:
    """
    Balance shipments across a fleet with OR-Tools CP-SAT by minimizing the
    peak vehicle utilization, respecting capacity, and carrying as much as
    possible.
    """

    def __init__(self, settings: OptimizationSettings | None = None):
        self.settings = settings or get_optimization_settings()

    def solve(
        self,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
    ) -> FleetUtilizationSolution:
        """Return a FleetUtilizationSolution for the given shipments/vehicles."""
        with Timer() as timer:
            solution = self._solve_inner(shipments, vehicles)
        solution.execution_time_ms = timer.elapsed_ms
        return solution

    def _solve_inner(
        self,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
    ) -> FleetUtilizationSolution:
        if not shipments:
            return FleetUtilizationSolution(
                success=True, status="OPTIMAL", message="No shipments to balance."
            )

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

        for warehouse_id, wh_ships in ships_by_wh.items():
            wh_vehicles = vehicles_by_wh.get(warehouse_id, [])
            if not wh_vehicles:
                unassigned.extend(s.shipment_id for s in wh_ships)
                continue
            status, assignments, loads, wh_unassigned = self._balance_one_warehouse(
                warehouse_id, wh_ships, wh_vehicles
            )
            worst_status = self._merge_status(worst_status, status)
            all_assignments.extend(assignments)
            all_loads.extend(loads)
            unassigned.extend(wh_unassigned)

        return self._build_solution(worst_status, all_assignments, all_loads, unassigned)

    def _balance_one_warehouse(
        self,
        warehouse_id: str | None,
        shipments: list[ShipmentInput],
        vehicles: list[VehicleInput],
    ) -> tuple[str, list[ShipmentAssignment], list[VehicleLoad], list[str]]:
        model = cp_model.CpModel()
        n_ships = len(shipments)
        n_vehicles = len(vehicles)
        demand = [max(0, int(s.package_count or 0)) for s in shipments]
        capacity = [max(0, int(v.capacity_packages or 0)) for v in vehicles]

        x = [
            [model.NewBoolVar(f"x_{s}_{v}") for v in range(n_vehicles)]
            for s in range(n_ships)
        ]
        # assigned[s] = 1 if shipment s is carried by ANY vehicle.
        assigned = [model.NewBoolVar(f"assigned_{s}") for s in range(n_ships)]
        # peak utilization across the fleet, in per-mille (0..1000).
        peak = model.NewIntVar(0, _PER_MILLE, "peak")

        for s in range(n_ships):
            model.Add(sum(x[s][v] for v in range(n_vehicles)) == assigned[s])

        for v in range(n_vehicles):
            load_v = sum(demand[s] * x[s][v] for s in range(n_ships))
            model.Add(load_v <= capacity[v])
            # peak >= utilization of vehicle v  <=>  load*1000 <= peak*capacity.
            if capacity[v] > 0:
                model.Add(load_v * _PER_MILLE <= peak * capacity[v])

        # Carry as much as possible first (BIG penalty on unassigned packages),
        # then make the fleet as balanced as possible (small penalty on peak).
        unassigned_packages = sum(
            demand[s] * (1 - assigned[s]) for s in range(n_ships)
        )
        big = _PER_MILLE + 1  # any unassigned package outweighs the whole peak.
        model.Minimize(big * unassigned_packages + peak)

        solver = self._make_solver()
        result = solver.Solve(model)
        status = _CP_STATUS_NAMES.get(result, "UNKNOWN")

        if result not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return status, [], [], [s.shipment_id for s in shipments]

        assignments: list[ShipmentAssignment] = []
        unassigned_ids: list[str] = []
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
                unassigned_ids.append(shipments[s].shipment_id)

        loads = [
            self._make_load(vehicles[v], loaded_packages[v], loaded_ships[v])
            for v in range(n_vehicles)
        ]
        return status, assignments, loads, unassigned_ids

    def _make_solver(self) -> cp_model.CpSolver:
        """A CP-SAT solver configured from the optimization settings.

        Mirrors the assignment solver: a fixed random seed is always set, and
        reproducible-benchmark mode (BENCHMARK_DETERMINISTIC) forces a single
        search worker and stops on DETERMINISTIC time (not wall-clock) so
        repeated runs and different machines agree. Production requests keep
        their many workers and the existing wall-clock time limit.
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
        order = {"OPTIMAL": 0, "FEASIBLE": 1, "UNKNOWN": 2, "INFEASIBLE": 3, "MODEL_INVALID": 4}
        return current if order.get(current, 2) >= order.get(incoming, 2) else incoming

    def _build_solution(
        self,
        status: str,
        assignments: list[ShipmentAssignment],
        loads: list[VehicleLoad],
        unassigned: list[str],
    ) -> FleetUtilizationSolution:
        used_loads = [load for load in loads if load.assigned_shipments > 0]
        utils = [load.utilization for load in used_loads]
        avg_util = safe_divide(sum(utils), len(utils), default=0.0)
        min_util = min(utils) if utils else 0.0
        max_util = max(utils) if utils else 0.0

        overloaded = sum(1 for load in used_loads if load.is_overloaded)
        underutilized = sum(1 for load in used_loads if load.is_underutilized)

        success = status in ("OPTIMAL", "FEASIBLE")
        message = (
            f"Balanced {len(assignments)} shipment(s) across {len(used_loads)} "
            f"vehicle(s); utilization spread {as_percent(max_util - min_util)} "
            f"points (avg {as_percent(avg_util)}%)."
        )
        return FleetUtilizationSolution(
            success=success,
            status=status,
            assignments=assignments,
            vehicle_loads=loads,
            unassigned_shipments=unassigned,
            average_utilization=round(avg_util, 4),
            min_utilization=round(min_util, 4),
            max_utilization=round(max_util, 4),
            utilization_spread=round(max_util - min_util, 4),
            overloaded_vehicles=overloaded,
            underutilized_vehicles=underutilized,
            vehicles_used=len(used_loads),
            message=message,
        )


# A ready-to-use instance for the common case (default settings).
vehicle_optimizer = VehicleOptimizer()
