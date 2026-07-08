"""
============================================================================
OPTIMIZATION ROUTER  (Week 5)   URL prefix: /optimize
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for the Week 5 optimization engine. THIN, exactly like the seven
Week 4 entity routers: each endpoint reads the request, calls one method on
optimization_service, and returns the result. No optimization logic and no
database access live here.

  GET  /optimize/status      is the engine ready? what can it do?
  POST /optimize/assignment  assign a warehouse's shipments to its vehicles
  POST /optimize/warehouse   pick the nearest in-stock warehouse per demand
  POST /optimize/fleet       balance shipments evenly across the fleet
  POST /optimize/routes      order a warehouse's stops into a short route

WHY POST FOR THE OPTIMIZERS (and GET for status)?
  The optimizers take a request BODY describing what to optimize (which
  warehouse, how many shipments, an explicit demand list) and perform a
  computation, so POST is the natural verb. `status` only reads fixed
  capability info and changes nothing, so it is a GET.

RESPONSES (as the Week 5 prompt asks) report, per problem: success, cost,
distance, vehicle utilization, unassigned shipments, and execution time - all
carried on the response models in api/schemas/optimization.py.
============================================================================
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas.optimization import (
    AssignmentRequest,
    AssignmentResponse,
    FleetRequest,
    FleetResponse,
    OptimizationStatusResponse,
    RouteResponse,
    RoutesRequest,
    WarehouseSelectionRequest,
    WarehouseSelectionResponse,
)
from api.services.optimization_service import optimization_service
from optimization.solution_models import DemandInput

router = APIRouter(prefix="/optimize", tags=["Optimization"])


@router.get(
    "/status",
    response_model=OptimizationStatusResponse,
    summary="Optimization engine readiness and capabilities",
)
def optimization_status():
    """Return the engine version, the solvers available, and the live settings."""
    return optimization_service.status()


@router.post(
    "/assignment",
    response_model=AssignmentResponse,
    summary="Assign shipments to vehicles (respects capacity; minimizes unused capacity)",
)
def optimize_assignment(
    payload: AssignmentRequest | None = None,
    db: Session = Depends(get_db),
):
    """Assign a warehouse's waiting shipments to its available vehicles."""
    req = payload or AssignmentRequest()
    return optimization_service.optimize_assignment(
        db, warehouse_id=req.warehouse_id, max_shipments=req.max_shipments
    )


@router.post(
    "/warehouse",
    response_model=WarehouseSelectionResponse,
    summary="Choose the nearest in-stock warehouse for each demand (else pending)",
)
def optimize_warehouse(
    payload: WarehouseSelectionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Pick the nearest operating, in-stock warehouse for each demand."""
    req = payload or WarehouseSelectionRequest()

    demands = None
    if req.demands is not None:
        # Map the request items into the engine's DemandInput dataclass,
        # generating a demand id where the caller did not supply one.
        demands = [
            DemandInput(
                demand_id=item.demand_id or f"DEM-{i:04d}",
                product_id=item.product_id,
                quantity=item.quantity,
                destination_city=item.destination_city,
                destination_state=item.destination_state,
                destination_latitude=item.destination_latitude,
                destination_longitude=item.destination_longitude,
            )
            for i, item in enumerate(req.demands)
        ]

    return optimization_service.select_warehouses(
        db,
        demands=demands,
        sample_size=req.sample_size,
        reserve_inventory=req.reserve_inventory,
    )


@router.post(
    "/fleet",
    response_model=FleetResponse,
    summary="Balance shipments across the fleet (avoids overloaded / idle vehicles)",
)
def optimize_fleet(
    payload: FleetRequest | None = None,
    db: Session = Depends(get_db),
):
    """Spread a warehouse's shipments evenly across its available vehicles."""
    req = payload or FleetRequest()
    return optimization_service.optimize_fleet(
        db, warehouse_id=req.warehouse_id, max_shipments=req.max_shipments
    )


@router.post(
    "/routes",
    response_model=RouteResponse,
    summary="Order a warehouse's delivery stops into a short route (nearest neighbour)",
)
def optimize_routes(
    payload: RoutesRequest | None = None,
    db: Session = Depends(get_db),
):
    """Order a warehouse's delivery stops into a short route."""
    req = payload or RoutesRequest()
    return optimization_service.optimize_routes(
        db,
        warehouse_id=req.warehouse_id,
        max_stops=req.max_stops,
        strategy=req.strategy,
    )
