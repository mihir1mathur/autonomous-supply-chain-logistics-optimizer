"""
============================================================================
optimization/ package  (Week 5)   -- the OPTIMIZATION ENGINE
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT LIVES HERE
---------------
  The Week 5 optimization engine: a small, self-contained, database-free
  toolkit that turns supply-chain questions into decisions using Google
  OR-Tools (CP-SAT) and simple heuristics. It is DELIBERATELY independent of
  FastAPI and SQLAlchemy - the API service layer feeds it plain data objects
  and shapes its results into JSON. That separation (SOLID dependency
  inversion) is what lets Week 7's CrewAI agents call the SAME engine directly.

THE FOUR OPTIMIZATION PROBLEMS (one solver each)
------------------------------------------------
  assignment_solver.py  - assign shipments to vehicles, respecting capacity,
                          minimizing unused capacity (consolidate). CP-SAT.
  warehouse_selector.py - choose the nearest in-stock, operating warehouse for
                          each demand; mark it pending if none. Greedy.
  vehicle_optimizer.py  - balance shipments across the fleet, minimizing the
                          peak vehicle utilization (spread). CP-SAT.
  route_optimizer.py    - order a warehouse's delivery stops into a short route
                          (nearest-neighbour), with a VRP interface reserved.

THE SUPPORTING MODULES
----------------------
  config.py           - tunable settings (solver time limit, thresholds, caps).
  utils.py            - haversine distance, a Timer, safe maths, simulated demand.
  cost_functions.py   - how a plan is PRICED (travel cost, unused capacity, ...).
  constraints.py      - the RULES a plan must obey (capacity, inventory).
  solution_models.py  - the plain input/output dataclasses the solvers speak in.

HOW A CALLER USES IT (the shape every solver shares)
----------------------------------------------------
      from optimization import assignment_solver
      from optimization.solution_models import ShipmentInput, VehicleInput
      result = assignment_solver.solve(shipments, vehicles)
      print(result.success, result.average_vehicle_utilization)

  Each solver exposes a class (AssignmentSolver, ...) AND a ready-made default
  instance (assignment_solver, ...) for the common case, mirroring how the Week
  4 services expose both a class and a singleton.
============================================================================
"""

from optimization.assignment_solver import AssignmentSolver, assignment_solver
from optimization.route_optimizer import RouteOptimizer, route_optimizer
from optimization.vehicle_optimizer import VehicleOptimizer, vehicle_optimizer
from optimization.warehouse_selector import WarehouseSelector, warehouse_selector

__all__ = [
    "AssignmentSolver",
    "assignment_solver",
    "WarehouseSelector",
    "warehouse_selector",
    "VehicleOptimizer",
    "vehicle_optimizer",
    "RouteOptimizer",
    "route_optimizer",
]
