"""
============================================================================
REUSABLE VALIDATION & ALLOWED-VALUE LISTS (ENUMS)  (Week 4)
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE HOLDS
--------------------
  The lists of ALLOWED VALUES for the "status"-style columns, taken directly
  from the Week 2 simulation rules and the Week 3 model comments. Keeping them
  here (once) means the Pydantic schemas, the services, and the docs all agree
  on exactly which values are legal - there is a single source of truth.

WHY USE ENUMS?
--------------
  An enum ("enumeration") is a fixed set of choices. A vehicle's
  availability_status can ONLY be available / on_delivery / maintenance - never
  "free" or "busy" or a typo. Declaring that as an enum means Pydantic rejects
  anything else automatically (a clean 422), and editors/Swagger show the exact
  choices. This is the same idea as the CHECK-constraint values documented in
  Week 3, enforced now at the API boundary before bad data can ever reach the
  database.

  We define them as `str, Enum` subclasses so they behave like plain strings
  (JSON-friendly) but with a locked set of members.

THE STOCK RULE (reused verbatim from Week 2 / Week 3 crud.py)
-------------------------------------------------------------
  out_of_stock  if stock_level <= 0
  low_stock     if stock_level <= reorder_threshold
  healthy       otherwise
  recompute_inventory_status() below mirrors _recompute_inventory_status() in
  database/crud.py so the API and the database layer never disagree.
============================================================================
"""

from enum import Enum


# ===========================================================================
# ALLOWED-VALUE ENUMS  (mirroring the Week 2/3 model comments)
# ===========================================================================
class OperatingStatus(str, Enum):
    """warehouses.operating_status"""

    active = "active"
    overloaded = "overloaded"
    inactive = "inactive"


class InventoryStatus(str, Enum):
    """inventory.inventory_status (derived from the stock rule)."""

    healthy = "healthy"
    low_stock = "low_stock"
    out_of_stock = "out_of_stock"


class VehicleType(str, Enum):
    """vehicles.vehicle_type"""

    van = "van"
    small_truck = "small_truck"
    medium_truck = "medium_truck"
    large_truck = "large_truck"


class AvailabilityStatus(str, Enum):
    """vehicles.availability_status"""

    available = "available"
    on_delivery = "on_delivery"
    maintenance = "maintenance"


class RouteStatus(str, Enum):
    """delivery_routes.route_status"""

    planned = "planned"
    in_transit = "in_transit"
    completed = "completed"


class DisruptionType(str, Enum):
    """disruptions.disruption_type"""

    heavy_traffic = "heavy_traffic"
    severe_weather = "severe_weather"
    warehouse_overload = "warehouse_overload"
    inventory_shortage = "inventory_shortage"
    road_closure = "road_closure"


class Severity(str, Enum):
    """disruptions.severity"""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DisruptionStatus(str, Enum):
    """disruptions.status"""

    active = "active"
    resolved = "resolved"
    scheduled = "scheduled"


# ===========================================================================
# SHARED BUSINESS RULE  (kept identical to database/crud.py Week 3)
# ===========================================================================
def recompute_inventory_status(stock_level: int, reorder_threshold: int) -> str:
    """
    Return the correct inventory_status for a stock level, using the SAME rule
    as Week 2 and database/crud.py. The service layer calls this after any stock
    change so stock_level and inventory_status can never drift apart.
    """
    if stock_level <= 0:
        return InventoryStatus.out_of_stock.value
    if stock_level <= reorder_threshold:
        return InventoryStatus.low_stock.value
    return InventoryStatus.healthy.value
