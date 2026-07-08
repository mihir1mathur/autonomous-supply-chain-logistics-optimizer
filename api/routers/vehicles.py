"""
============================================================================
VEHICLES ROUTER  (Week 4)   URL prefix: /vehicles
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for vehicles (the delivery FLEET). Thin: calls vehicle_service.
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate
from api.services.vehicle_service import vehicle_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get(
    "",
    response_model=PaginatedResponse[VehicleResponse],
    summary="List vehicles (filter, search, sort, paginate)",
)
def list_vehicles(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    warehouse_id: str | None = Query(None, description="Filter by home warehouse."),
    vehicle_type: str | None = Query(None, description="Filter by vehicle type."),
    availability_status: str | None = Query(
        None, description="Filter by available / on_delivery / maintenance."
    ),
):
    """Return a page of vehicles with optional filters, search, and sorting."""
    return vehicle_service.list(
        db,
        params,
        filters={
            "warehouse_id": warehouse_id,
            "vehicle_type": vehicle_type,
            "availability_status": availability_status,
        },
        search=search,
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse, summary="Get one vehicle by id")
def get_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    return vehicle_service.get(db, vehicle_id)


@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new vehicle",
)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    return vehicle_service.create(db, payload.model_dump())


@router.put("/{vehicle_id}", response_model=VehicleResponse, summary="Replace a vehicle")
def replace_vehicle(vehicle_id: str, payload: VehicleUpdate, db: Session = Depends(get_db)):
    return vehicle_service.update(db, vehicle_id, payload.model_dump(exclude_unset=True))


@router.patch("/{vehicle_id}", response_model=VehicleResponse, summary="Partially update a vehicle")
def update_vehicle(vehicle_id: str, payload: VehicleUpdate, db: Session = Depends(get_db)):
    return vehicle_service.update(db, vehicle_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a vehicle",
)
def delete_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    vehicle_service.delete(db, vehicle_id)
