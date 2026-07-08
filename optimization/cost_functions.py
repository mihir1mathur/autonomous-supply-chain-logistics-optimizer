"""
============================================================================
COST FUNCTIONS  (Week 5)   -- how we PRICE a decision
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT A "COST FUNCTION" IS (zero-knowledge version)
--------------------------------------------------
  An optimizer chooses between many possible plans. To choose, it needs a way
  to score each plan with a single number - the COST - and then prefer the
  plan with the lowest cost (or, flipped, the highest value). A cost function
  is just that scoring rule. Here we keep those rules in ONE place so every
  solver prices things the same way and the scoring is easy to read and test.

WHAT WE PRICE IN WEEK 5
-----------------------
  - travel cost of a leg   = road distance (km) * the vehicle's cost_per_km
  - unused capacity        = capacity a vehicle carries but does not use
  - utilization            = how full a vehicle is (0..1), and the fleet spread
  These mirror the Week 2 route economics (distance * a per-km rate) so the
  numbers stay comparable to the stored estimates.

WHY PURE FUNCTIONS
------------------
  Every function here is pure (inputs -> number, no database, no OR-Tools).
  That keeps the "what does good mean?" question separate from the "how do we
  search?" machinery in the solvers - and makes each rule unit-testable.
============================================================================
"""

from __future__ import annotations

from optimization.solution_models import VehicleLoad
from optimization.utils import DEFAULT_WINDING_FACTOR, road_distance_km, safe_divide


def travel_cost(distance_km: float, cost_per_km: float | None) -> float:
    """
    Price one trip: distance travelled times the vehicle's per-km rate.
    A missing rate is treated as 0 so a lack of data cannot inflate the cost.
    """
    return distance_km * (cost_per_km or 0.0)


def leg_cost_between(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    cost_per_km: float | None,
    winding_factor: float = DEFAULT_WINDING_FACTOR,
) -> float:
    """
    Convenience: the travel cost between two coordinates, using the same
    road-distance estimate (haversine * winding factor) as the rest of Week 5.
    """
    distance = road_distance_km(lat1, lon1, lat2, lon2, winding_factor)
    return travel_cost(distance, cost_per_km)


def unused_capacity(capacity_packages: int, assigned_packages: int) -> int:
    """
    The slack left on a vehicle: capacity it carries around but does not use.
    Minimising the total of this across the fleet is what "minimize unused
    capacity" (the Shipment Assignment goal) means in practice - it rewards
    consolidating shipments onto fewer, fuller vehicles.
    """
    return max(0, capacity_packages - assigned_packages)


def utilization_fraction(assigned_packages: int, capacity_packages: int) -> float:
    """
    How full a vehicle is, as a 0..1 fraction (assigned / capacity). Returns 0
    for a vehicle with no capacity so the maths is always safe.
    """
    return safe_divide(assigned_packages, capacity_packages, default=0.0)


def total_unused_capacity(loads: list[VehicleLoad]) -> int:
    """Sum of unused capacity over every vehicle that carried something."""
    return sum(load.unused_capacity for load in loads if load.assigned_shipments > 0)


def average_utilization(loads: list[VehicleLoad]) -> float:
    """
    Average utilization across the vehicles that were actually USED (carried at
    least one shipment). Empty vehicles are excluded so they do not drag the
    average to zero and hide how full the working fleet is.
    """
    used = [load.utilization for load in loads if load.assigned_shipments > 0]
    return safe_divide(sum(used), len(used), default=0.0)
