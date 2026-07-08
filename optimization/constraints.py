"""
============================================================================
CONSTRAINTS  (Week 5)   -- the RULES a valid plan must obey
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT A "CONSTRAINT" IS (zero-knowledge version)
-----------------------------------------------
  A cost function (cost_functions.py) says which plans are BETTER. A constraint
  says which plans are even ALLOWED. "A vehicle may not carry more than its
  capacity" is a constraint: any plan that breaks it is invalid, no matter how
  cheap it looks. Optimization = find the cheapest plan AMONG the allowed ones.

WHY GATHER THE RULES HERE
-------------------------
  The business rules of Week 5 live in this one file as small, readable,
  pure predicate functions:
    - vehicle capacity        (a vehicle's load must fit its capacity)
    - warehouse inventory      (a warehouse must actually hold enough stock)
    - warehouse operating      (only an active warehouse may be chosen)
  The solvers translate these SAME rules into the language OR-Tools speaks
  (linear inequalities), and the plain-Python versions here let scripts and
  tests check any finished plan for violations without a solver. One source of
  truth, checked two ways.

  These mirror the Week 2/Week 3 domain: vehicles.capacity_packages is a hard
  limit; inventory.stock_level is what a warehouse can ship; a warehouse whose
  operating_status is not "active" is treated as unavailable.
============================================================================
"""

from __future__ import annotations

from optimization.solution_models import (
    DemandInput,
    ShipmentInput,
    VehicleInput,
    WarehouseInput,
)

# A warehouse is only usable if it is operating normally. "overloaded" and
# "inactive" (the other Week 2 statuses) are treated as unavailable so we never
# route new work to a warehouse that cannot take it.
USABLE_WAREHOUSE_STATUS = "active"


# ===========================================================================
# CAPACITY  -- does a set of shipments fit on a vehicle?
# ===========================================================================
def packages_demanded(shipments: list[ShipmentInput]) -> int:
    """Total package count across a group of shipments."""
    return sum(int(s.package_count or 0) for s in shipments)


def fits_capacity(shipments: list[ShipmentInput], vehicle: VehicleInput) -> bool:
    """
    True if these shipments can all travel on this vehicle without exceeding
    its package capacity. This is the exact rule the assignment/fleet solvers
    enforce as `sum(load) <= capacity` inside OR-Tools.
    """
    return packages_demanded(shipments) <= int(vehicle.capacity_packages or 0)


def capacity_violation(shipments: list[ShipmentInput], vehicle: VehicleInput) -> int:
    """
    How many packages OVER capacity this group is (0 if it fits). Used by the
    validators to report the size of a breach, not just that one happened.
    """
    over = packages_demanded(shipments) - int(vehicle.capacity_packages or 0)
    return max(0, over)


# ===========================================================================
# INVENTORY  -- can a warehouse actually supply a demand?
# ===========================================================================
def has_sufficient_inventory(available_stock: int, quantity_needed: int) -> bool:
    """
    True if a warehouse holds at least as many units as the demand needs.
    `available_stock` is the inventory.stock_level for that (warehouse, product).
    """
    return int(available_stock or 0) >= int(quantity_needed or 0)


def is_warehouse_usable(warehouse: WarehouseInput) -> bool:
    """
    True if a warehouse may be selected: it must be operating ("active"). A
    warehouse that is "overloaded" or "inactive" is skipped so we never send new
    demand somewhere that cannot handle it.
    """
    return (warehouse.operating_status or "").lower() == USABLE_WAREHOUSE_STATUS


def can_warehouse_serve(
    warehouse: WarehouseInput,
    demand: DemandInput,
    available_stock: int,
) -> bool:
    """
    The full warehouse-selection rule in one call: the warehouse must be usable
    AND hold enough stock of the demanded product. This is exactly what the
    warehouse selector checks before considering a warehouse a candidate.
    """
    return is_warehouse_usable(warehouse) and has_sufficient_inventory(
        available_stock, demand.quantity
    )


# ===========================================================================
# VALIDATION  -- count violations in a FINISHED plan (used by tests/validators)
# ===========================================================================
def count_capacity_violations(
    grouped: dict[str, list[ShipmentInput]],
    vehicles_by_id: dict[str, VehicleInput],
) -> int:
    """
    Given a finished assignment (vehicle_id -> the shipments placed on it),
    count how many vehicles exceed their capacity. A correct solve must return
    0 here - the Week 5 validation script asserts exactly that.
    """
    violations = 0
    for vehicle_id, shipments in grouped.items():
        vehicle = vehicles_by_id.get(vehicle_id)
        if vehicle is None:
            # A shipment assigned to an unknown vehicle is itself a violation.
            violations += 1
            continue
        if not fits_capacity(shipments, vehicle):
            violations += 1
    return violations
