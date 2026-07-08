"""
============================================================================
OPTIMIZATION SCHEMAS  (Week 5)   endpoints: /optimize/*
Project: Supply Chain & Logistics Optimizer
============================================================================

WHAT THIS FILE HOLDS
--------------------
  The Pydantic REQUEST and RESPONSE schemas for the optimization endpoints -
  the JSON shape a caller sends and the JSON they get back. Same idea as the
  seven entity schema files from Week 4, but here the "response" objects mirror
  the plain dataclasses the optimization engine returns
  (optimization/solution_models.py) rather than a database table.

THE BRIDGE (from_attributes=True, reused from Week 4)
-----------------------------------------------------
  The service calls a solver, which returns a dataclass (e.g. AssignmentSolution
  with .assignments, .vehicle_loads, ...). Each Response schema below inherits
  ORMModel (from_attributes=True), so FastAPI builds the JSON by reading those
  attributes straight off the dataclass - exactly the way it reads a SQLAlchemy
  row. No manual conversion code is needed.

REQUEST DESIGN (why every field has a default)
----------------------------------------------
  Every request is happy with an empty body ("{}"): the service picks a
  sensible default warehouse / sample so a caller can try each endpoint with
  zero setup, then narrow it down (a specific warehouse, more shipments, an
  explicit demand list) as they learn. Sizes are clamped by the OPT_* caps in
  optimization/config.py, so a request can never build an unbounded model.
============================================================================
"""

from pydantic import BaseModel, Field

from api.schemas.base import ORMModel


# ===========================================================================
# REQUESTS
# ===========================================================================
class AssignmentRequest(BaseModel):
    """Assign a warehouse's waiting shipments to its vehicles."""

    warehouse_id: str | None = Field(
        None,
        description="Which warehouse to optimize. If omitted, the service picks "
        "a warehouse that has both vehicles and routes.",
    )
    max_shipments: int | None = Field(
        None,
        ge=1,
        description="Cap on how many shipments to include (clamped by "
        "OPT_MAX_SHIPMENTS_PER_REQUEST).",
    )


class FleetRequest(BaseModel):
    """Balance a warehouse's shipments evenly across its vehicles."""

    warehouse_id: str | None = Field(
        None, description="Which warehouse to balance. If omitted, one is chosen."
    )
    max_shipments: int | None = Field(
        None, ge=1, description="Cap on how many shipments to include."
    )


class DemandItem(BaseModel):
    """One 'deliver this much of this product to here' request."""

    product_id: str = Field(..., description="The product to fulfil.")
    quantity: int = Field(..., ge=1, description="Units required.")
    demand_id: str | None = Field(None, description="Optional id for this demand.")
    destination_latitude: float | None = Field(
        None, ge=-90, le=90, description="Destination latitude."
    )
    destination_longitude: float | None = Field(
        None, ge=-180, le=180, description="Destination longitude."
    )
    destination_city: str | None = Field(None, description="Destination city.")
    destination_state: str | None = Field(None, description="Destination state.")


class WarehouseSelectionRequest(BaseModel):
    """Choose the nearest in-stock warehouse for each demand."""

    demands: list[DemandItem] | None = Field(
        None,
        description="Explicit demands to place. If omitted, the service builds a "
        "sample of `sample_size` demands from real inventory and route "
        "destinations.",
    )
    sample_size: int | None = Field(
        None,
        ge=1,
        description="How many demands to auto-generate when `demands` is omitted "
        "(clamped by OPT_MAX_WAREHOUSE_DEMANDS_PER_REQUEST).",
    )
    reserve_inventory: bool = Field(
        True,
        description="If true, each fulfilment reduces the tracked stock so two "
        "demands cannot be promised the same units.",
    )


class RoutesRequest(BaseModel):
    """Order a warehouse's delivery stops into a short route."""

    warehouse_id: str | None = Field(
        None, description="Which warehouse's stops to route. If omitted, one is chosen."
    )
    max_stops: int | None = Field(
        None, ge=1, description="Cap on how many stops to include (clamped by config)."
    )
    strategy: str | None = Field(
        None,
        description="Routing strategy: 'nearest_neighbor' (default). 'vrp' is "
        "reserved for a future week.",
    )


# ===========================================================================
# SHARED RESPONSE PIECES
# ===========================================================================
class ShipmentAssignmentSchema(ORMModel):
    shipment_id: str
    vehicle_id: str
    warehouse_id: str | None = None
    package_count: int


class VehicleLoadSchema(ORMModel):
    vehicle_id: str
    warehouse_id: str | None = None
    capacity_packages: int
    assigned_packages: int
    assigned_shipments: int
    utilization: float
    unused_capacity: int
    is_overloaded: bool
    is_underutilized: bool


# ===========================================================================
# RESPONSES  (mirror optimization/solution_models.py dataclasses)
# ===========================================================================
class AssignmentResponse(ORMModel):
    success: bool
    status: str
    assignments: list[ShipmentAssignmentSchema] = []
    vehicle_loads: list[VehicleLoadSchema] = []
    unassigned_shipments: list[str] = []
    total_cost: float
    total_distance_km: float
    average_vehicle_utilization: float
    vehicles_used: int
    constraint_violations: int
    execution_time_ms: float
    message: str


class WarehouseChoiceSchema(ORMModel):
    demand_id: str
    product_id: str
    quantity: int
    selected_warehouse_id: str | None = None
    distance_km: float
    status: str
    reason: str


class WarehouseSelectionResponse(ORMModel):
    success: bool
    status: str
    choices: list[WarehouseChoiceSchema] = []
    assigned_count: int
    pending_count: int
    average_distance_km: float
    total_distance_km: float
    execution_time_ms: float
    message: str


class FleetResponse(ORMModel):
    success: bool
    status: str
    assignments: list[ShipmentAssignmentSchema] = []
    vehicle_loads: list[VehicleLoadSchema] = []
    unassigned_shipments: list[str] = []
    average_utilization: float
    min_utilization: float
    max_utilization: float
    utilization_spread: float
    overloaded_vehicles: int
    underutilized_vehicles: int
    vehicles_used: int
    execution_time_ms: float
    message: str


class RouteStopSchema(ORMModel):
    sequence: int
    node_id: str
    city: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    leg_distance_km: float
    cumulative_distance_km: float


class RouteResponse(ORMModel):
    success: bool
    status: str
    strategy: str
    warehouse_id: str | None = None
    stops: list[RouteStopSchema] = []
    total_distance_km: float
    naive_distance_km: float
    distance_reduction_km: float
    distance_reduction_percent: float
    stop_count: int
    execution_time_ms: float
    message: str


class OptimizationStatusResponse(BaseModel):
    """The engine's readiness/capability report for GET /optimize/status."""

    engine: str
    ortools_version: str
    available: bool
    solvers: list[str]
    route_strategies: list[str]
    settings: dict
