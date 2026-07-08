"""
============================================================================
SOLUTION MODELS  (Week 5)   -- the INPUT and OUTPUT shapes of the engine
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE HOLDS
--------------------
  Plain Python dataclasses that describe:
    1. The INPUTS a solver needs (a shipment, a vehicle, a warehouse, a
       demand) - small, database-free "data transfer objects".
    2. The OUTPUTS a solver returns (an assignment, a per-vehicle load, a
       route with ordered stops, and the four top-level "solution" objects).

WHY DATACLASSES, AND WHY NO DATABASE / NO FASTAPI HERE
------------------------------------------------------
  The solvers must not depend on SQLAlchemy or FastAPI. They speak ONLY in
  these plain objects. This is the Dependency-Inversion idea from SOLID: the
  optimization core depends on simple data, not on the web or the database.

    - The SERVICE layer (api/services/optimization_service.py) reads the Week 3
      database, maps rows into the INPUT dataclasses here, and calls a solver.
    - The solver returns an OUTPUT dataclass here.
    - The ROUTER shapes that output into JSON via a Pydantic response schema.

  Because the outputs are ordinary objects with attributes, Pydantic's
  `from_attributes=True` response schemas (Week 4 pattern) read them directly -
  the same bridge used for SQLAlchemy rows.

  Every output object also offers `as_dict()` so scripts (the Week 5 demo /
  validation) can print or serialise a solution without FastAPI.
============================================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


# ===========================================================================
# INPUTS  -- the minimal data each solver needs, free of any ORM/HTTP details
# ===========================================================================
@dataclass
class ShipmentInput:
    """One delivery to be carried: where it ships from and how big it is."""

    shipment_id: str            # e.g. a delivery_routes.route_id
    warehouse_id: str | None    # the origin warehouse it belongs to
    package_count: int          # units to carry (simulated; see utils.py)
    destination_city: str | None = None
    destination_state: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    weight_kg: float | None = None
    # The warehouse -> destination leg distance (km). Populated from the Week 2
    # delivery_routes.estimated_distance_km so cost/distance totals reuse the
    # existing estimate rather than recomputing it.
    distance_km: float | None = None


@dataclass
class VehicleInput:
    """One vehicle in the fleet and its hard capacity limits."""

    vehicle_id: str
    warehouse_id: str | None
    capacity_packages: int
    capacity_kg: float | None = None
    cost_per_km: float | None = None
    average_speed_kmph: float | None = None


@dataclass
class WarehouseInput:
    """One warehouse: where it is and whether it can operate."""

    warehouse_id: str
    latitude: float | None = None
    longitude: float | None = None
    capacity: int | None = None
    current_utilization: float | None = None
    operating_status: str | None = None


@dataclass
class DemandInput:
    """
    A request to fulfil a quantity of one product at a destination - the input
    to warehouse selection ("which warehouse should serve this?").
    """

    demand_id: str
    product_id: str
    quantity: int
    destination_city: str | None = None
    destination_state: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None


# ===========================================================================
# OUTPUTS  -- what each solver returns
# ===========================================================================
@dataclass
class ShipmentAssignment:
    """A single decision: this shipment travels on this vehicle."""

    shipment_id: str
    vehicle_id: str
    warehouse_id: str | None
    package_count: int

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class VehicleLoad:
    """How full one vehicle ended up after assignment."""

    vehicle_id: str
    warehouse_id: str | None
    capacity_packages: int
    assigned_packages: int
    assigned_shipments: int
    utilization: float          # assigned_packages / capacity_packages (0..1)
    unused_capacity: int        # capacity_packages - assigned_packages
    is_overloaded: bool = False
    is_underutilized: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class AssignmentSolution:
    """
    The result of SHIPMENT ASSIGNMENT: which shipment goes on which vehicle,
    how full each vehicle is, and the shipments that could not be placed.
    """

    success: bool
    status: str                 # solver status, e.g. "OPTIMAL" / "FEASIBLE"
    assignments: list[ShipmentAssignment] = field(default_factory=list)
    vehicle_loads: list[VehicleLoad] = field(default_factory=list)
    unassigned_shipments: list[str] = field(default_factory=list)
    total_cost: float = 0.0
    total_distance_km: float = 0.0
    average_vehicle_utilization: float = 0.0
    vehicles_used: int = 0
    constraint_violations: int = 0
    execution_time_ms: float = 0.0
    message: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class WarehouseChoice:
    """One warehouse-selection decision for a single demand."""

    demand_id: str
    product_id: str
    quantity: int
    selected_warehouse_id: str | None
    distance_km: float
    status: str                 # "assigned" or "pending"
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class WarehouseSelectionSolution:
    """
    The result of WAREHOUSE SELECTION: the nearest in-stock warehouse chosen
    for each demand, and the demands left pending (no warehouse had stock).
    """

    success: bool
    status: str
    choices: list[WarehouseChoice] = field(default_factory=list)
    assigned_count: int = 0
    pending_count: int = 0
    average_distance_km: float = 0.0
    total_distance_km: float = 0.0
    execution_time_ms: float = 0.0
    message: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class FleetUtilizationSolution:
    """
    The result of VEHICLE UTILIZATION balancing: shipments spread across the
    fleet to keep loads even, with the per-vehicle loads and balance metrics.
    """

    success: bool
    status: str
    assignments: list[ShipmentAssignment] = field(default_factory=list)
    vehicle_loads: list[VehicleLoad] = field(default_factory=list)
    unassigned_shipments: list[str] = field(default_factory=list)
    average_utilization: float = 0.0
    min_utilization: float = 0.0
    max_utilization: float = 0.0
    utilization_spread: float = 0.0   # max - min (lower is better balanced)
    overloaded_vehicles: int = 0
    underutilized_vehicles: int = 0
    vehicles_used: int = 0
    execution_time_ms: float = 0.0
    message: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class RouteStop:
    """One stop on an ordered route, with running distance totals."""

    sequence: int               # 0 = the warehouse start, then 1, 2, 3, ...
    node_id: str                # warehouse_id for the start, else shipment id
    city: str | None
    state: str | None
    latitude: float | None
    longitude: float | None
    leg_distance_km: float      # distance from the PREVIOUS stop to this one
    cumulative_distance_km: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class RouteSolution:
    """
    The result of ROUTE OPTIMIZATION: the order to visit the stops, the total
    optimized distance, and how much shorter that is than the naive order.
    """

    success: bool
    status: str
    strategy: str
    warehouse_id: str | None
    stops: list[RouteStop] = field(default_factory=list)
    total_distance_km: float = 0.0
    naive_distance_km: float = 0.0        # distance in the un-optimized order
    distance_reduction_km: float = 0.0
    distance_reduction_percent: float = 0.0
    stop_count: int = 0
    execution_time_ms: float = 0.0
    message: str = ""

    def as_dict(self) -> dict:
        return asdict(self)
