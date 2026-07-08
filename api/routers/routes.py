"""
============================================================================
ROUTES ROUTER  (Week 4)   URL prefix: /routes
Project: Supply Chain & Logistics Optimizer
============================================================================

REST endpoints for delivery routes (warehouse -> customer trips). Thin: calls
route_service.
============================================================================
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_db, pagination_params, search_query
from api.schemas.base import PaginatedResponse
from api.schemas.route import RouteCreate, RouteResponse, RouteUpdate
from api.services.route_service import route_service
from api.utils.pagination import PageParams

router = APIRouter(prefix="/routes", tags=["Delivery Routes"])


@router.get(
    "",
    response_model=PaginatedResponse[RouteResponse],
    summary="List delivery routes (filter, search, sort, paginate)",
)
def list_routes(
    db: Session = Depends(get_db),
    params: PageParams = Depends(pagination_params),
    search: str | None = Depends(search_query),
    warehouse_id: str | None = Query(None, description="Filter by origin warehouse."),
    customer_id: str | None = Query(None, description="Filter by destination customer."),
    order_id: str | None = Query(None, description="Filter by order."),
    vehicle_id: str | None = Query(None, description="Filter by assigned vehicle."),
    route_status: str | None = Query(
        None, description="Filter by planned / in_transit / completed."
    ),
):
    """Return a page of delivery routes with optional filters, search, sorting."""
    return route_service.list(
        db,
        params,
        filters={
            "warehouse_id": warehouse_id,
            "customer_id": customer_id,
            "order_id": order_id,
            "vehicle_id": vehicle_id,
            "route_status": route_status,
        },
        search=search,
    )


@router.get("/{route_id}", response_model=RouteResponse, summary="Get one delivery route by id")
def get_route(route_id: str, db: Session = Depends(get_db)):
    return route_service.get(db, route_id)


@router.post(
    "",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new delivery route",
)
def create_route(payload: RouteCreate, db: Session = Depends(get_db)):
    return route_service.create(db, payload.model_dump())


@router.put("/{route_id}", response_model=RouteResponse, summary="Replace a delivery route")
def replace_route(route_id: str, payload: RouteUpdate, db: Session = Depends(get_db)):
    return route_service.update(db, route_id, payload.model_dump(exclude_unset=True))


@router.patch("/{route_id}", response_model=RouteResponse, summary="Partially update a delivery route")
def update_route(route_id: str, payload: RouteUpdate, db: Session = Depends(get_db)):
    return route_service.update(db, route_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a delivery route",
)
def delete_route(route_id: str, db: Session = Depends(get_db)):
    route_service.delete(db, route_id)
